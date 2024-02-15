import os
import sys
import openai
from openai import AzureOpenAI
import logging
from logging.handlers import TimedRotatingFileHandler
from logging import DEBUG, INFO
import argparse
import csv
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from string import Template
from utils import file_utils, variant_utils
from pandas import read_excel
import time
import re
import json
import pathlib
from typing import List, Dict, Optional, Any

CSV_COLUMNS = [
    'id',
    'file_name',
    'system_message',
    'prompt_id',
    'prompt',
    'answer',
    'variant',
    'gene',
    'expected_outcomes',
    'prompt_tokens',
    'completion_tokens',
    'estimated_cost',
    'system_fingerprint',
    'timestamp'
]

KEY_SYSMSG = "system_message"
KEY_QUESTIONS = "questions"
KEY_QUESTION = "question"
KEY_QUESTION_ID = "id"
KEY_STOP_CONDITION = "stop_condition"
KEY_RESP_REGEX = "response_regex"

class PromptExecutor:
    def __init__(self, args, gpt_deployment: str):
        self.publicationid: str = args.publicationId
        self.sleep_at_each_publication: int = args.sleepAtEachPublication
        self.use_mock: bool = args.useMock
        self.publications_parameters: Dict[str, Any] = self.__read_publication_configs(args.fileConfig)
        self.questions_parameters: Dict = self.__read_question_configs(args.questionConfig)
        self.result_file_path: str = self.__setup_result_file()
        self.gpt_deployment: str = gpt_deployment
        self.temperature: int = args.temperature
        self.max_tokens: int = args.maxTokens

    def process(self) -> None:
        """
        Process publications in PDF as per configuration
        """
        if self.publicationid:
            # Only process the publication specified in the argument
            self.__handle_single_publication(self.publicationid)
        else:
            # Process all files included in the specified folder
            count = 0
            for id in self.publications_parameters:
                self.__handle_single_publication(id)
                count += 1
                if (self.sleep_at_each_publication and self.sleep_at_each_publication >= 0
                    and count < len(self.publications_parameters)):
                    logging.info(f'Sleeping for {self.sleep_at_each_publication} seconds')
                    time.sleep(self.sleep_at_each_publication)
                    logging.debug('Awake from the sleep')

    def __handle_single_publication(self, publication_id: str) -> None:
        """
        Handles processing of a single publication

        :param publication_id: id of publication specified in the publication param configs
        """
        logging.info(f'** Start processing publication Id: {publication_id}\n')

        publication = self.publications_parameters[publication_id]
        if publication:
            file_path = os.path.join(publication['file_path'], publication['file_name'])
            variant = publication['variant']
            gene = publication['gene']
            variant_aliases = publication['variant_aliases']
            variants_parsed = [s.strip() for s in variant_aliases.split(',')]
            expected_outcome = publication['expected_outcomes']

            if file_path and variant and gene and Path(file_path).suffix == '.pdf':
                self.__execute_sequential_prompts(publication_id, file_path, variant, gene, variants_parsed, expected_outcome)
            else:
                logging.error(
                    f'Required metadata missing for the publication: id={publication_id}')
        else:
            logging.error(
                f'Cannot find the publication: id={publication_id}')
        
        logging.info(f'** End processing publication Id: {publication_id}\n')         

    def __execute_sequential_prompts(
            self,
            publication_id: str,
            pdf_filepath: str,
            variant: str,
            gene: str,
            variant_aliases: List[str],
            expected_outcome: str) -> None:
        """
        Executes a set of prompts configured for the given publication

        :param publication_id: id of publication specified in the publication param configs
        :param pdf_filepath: file location of the publication
        :param variant: target variant
        :param gene: target gene
        :param variant_aliases: list of variant nomenclature aliases equivalent to the target variant
        :param expected_outcome: expected final outcome from running the prompts for comparison
        """
        logging.debug(f"Id: '{publication_id}', File Path: '{pdf_filepath}', Variant: '{variant}', Gene: '{gene}'")

        # Convert PDF to text
        pdf_in_text = file_utils.convert_pdf_to_txt(pdf_filepath)

        # Find the longest variant that appears in PDF
        variant_perms = variant_aliases.copy()
        variant_perms.append(variant)
        longest_variant = variant_utils.find_longest_matching_variant(pdf_in_text, variant_perms)
        logging.info(f'Variants: {variant_perms}')
        logging.info(f'Longest Variant: {longest_variant}')

        # Initialize with a sysmtem message
        system_message = self.questions_parameters[KEY_SYSMSG]
        if '$param' in system_message:
            system_message = Template(system_message).substitute(param_variant=variant, param_gene=gene, param_variant_aliases=", ".join(variant_aliases))
        
        messages = [
            { 
                "role": "system",
                "content": system_message
            }
        ]
        logging.info('> System: ' + messages[0]['content'] + '\n')

        # Get a list of configured questions (prompts)
        questions = self.questions_parameters[KEY_QUESTIONS]

        # Initialize input parameters
        input_params = {
            'index': 0,
            'param_gene': gene,
            'content': pdf_in_text,
            'publication_id': publication_id,
            'pdf_filepath': pdf_filepath,
            'system_message': system_message,
            'expected_outcome': expected_outcome
        }

        # Find variant using question #1 (with content included) and #2 (without content)
        variant_with_evidence = self.__execute_prompt_for_functional_evidence(variant, longest_variant, questions, messages, input_params)

        # If functional evidence was found, ask remaining questions
        if variant_with_evidence:
            index = input_params['index'] + 1
            should_stop = False
            for item in questions[2:]:
                index += 1
                if should_stop:
                    break

                id = item[KEY_QUESTION_ID] if KEY_QUESTION_ID in item else index
                stop_condition = None
                if KEY_STOP_CONDITION in item and KEY_RESP_REGEX in item[KEY_STOP_CONDITION]:
                    stop_condition = item[KEY_STOP_CONDITION][KEY_RESP_REGEX]

                result = self.__execute_single_prompt(item, variant_with_evidence, messages, input_params)

                # Check if the stopping condition exists and has been satisfied
                if stop_condition:
                    found = re.search(stop_condition, result['answer'])
                    if found:
                        logging.info(f'Stopping condition {stop_condition} has been satisfied: match={found}')
                        should_stop = True
    
    def __execute_prompt_for_functional_evidence(
            self,
            variant: str,
            longest_variant: Optional[str],
            questions: List[Dict],
            messages: List[Dict],
            input_params: Dict) -> Optional[str]:
        """
        Handles special logic to look for functional evidence by using 3 different variation of the target variant.

        1. Longest variant: longest variant representation from the alias list used in the publication
        2. Target variant: target variant specified in the input parameter
        3. Gene-prefixed variant: gene-variant combination 

        :param variant: target variant
        :param longest_variant: longest variant representation
        :param questions: list of questions configured
        :param input_params: set of input parameters

        :return variant_with_evidence: variant used to find functional evidence

        If no variant with evidence exists, it returns None
        """

        # Find variant using question #1 (with content included) and #2 (without content)
        question_with_content = questions[0]
        regex_with_content = question_with_content[KEY_STOP_CONDITION][KEY_RESP_REGEX]
        question_without_content = questions[1]
        regex_without_content = question_without_content[KEY_STOP_CONDITION][KEY_RESP_REGEX]

        gene = input_params['param_gene']
        prompts_to_execute = []
        if longest_variant is not None and longest_variant != variant:
            # Longest variant is found in the publication, that's different from the target variant
            prompts_to_execute.append({
                'question': question_with_content,
                'variant': longest_variant,
                'regex_condition': regex_with_content,
                'description': 'Longest Variant'
            })
            prompts_to_execute.append({
                'question': question_without_content,
                'variant': variant,
                'regex_condition': regex_without_content,
                'description': 'Original Variant'
            })
        else:
            prompts_to_execute.append({
                'question': question_with_content,
                'variant': variant,
                'regex_condition': regex_with_content,
                'description': 'Original Variant'
            })
        prompts_to_execute.append({
            'question': question_without_content,
            'variant': f'{gene} {variant}',
            'regex_condition': regex_without_content,
            'description': 'Gene + Langest Variant'
        })

        # Execute prompts as configured, until the regex condition is not met
        # or exhausted the maxium # of attempts to find functional evidence
        variant_with_evidence = None
        for i, prompt in enumerate(prompts_to_execute):
            logging.info('Searching for Functional Evidence Attept #' + str(i+1) + ': ' + prompt['description'] + '\n')
            result = self.__execute_single_prompt(prompt['question'], prompt['variant'], messages, input_params)

            no_evidence = re.search(prompt['regex_condition'], result['answer'])
            # Check if functional evidence has been found
            if not no_evidence:
                variant_with_evidence = prompt['variant']
                break

        return variant_with_evidence
    
    def __execute_single_prompt(
            self,
            question: Dict,
            variant: str,
            messages: List[Dict],
            input_params: Dict) -> Dict:
        """
        Helper method to execute a single prompt

        :param question: prompt to execute
        :param variant: variant
        :param messages: GPT chat history
        :param input_params: set of input parameters

        :return result: result of executing the prompt
        """
        input_params['index'] = input_params['index'] + 1 # Increment index

        index = input_params['index']
        gene = input_params['param_gene']
        pdf_in_text = input_params['content']
        publication_id = input_params['publication_id']
        pdf_filepath = input_params['pdf_filepath']
        system_message = input_params['system_message']
        expected_outcome = input_params['expected_outcome']

        prompt_template = question[KEY_QUESTION]
        id = question[KEY_QUESTION_ID]
        logging.info(f'##### Start prompt #{id}')

        # Set up the next prompt
        prompt = Template(prompt_template).substitute(param_variant=variant, param_gene=gene, content=pdf_in_text)
        messages.append({
            "role": "user",
            "content": prompt
        })
        size_limit = min(len(messages[-1]['content']), 300)
        logging.info('> Human: ' + re.sub('\s+', ' ', messages[-1]['content'][:size_limit]) + ' ...')

        # Call OpenAI
        response = self.__call_openapi_chat_completion(messages)

        # Append response to the messages to retain previous context
        usage = response.usage
        system_fingerprint = response.system_fingerprint
        message = response.choices[0].message
        messages.append(message)
        logging.info('> AI: ' + message.content)
        logging.info('Completion Tokens: ' + str(usage.completion_tokens) + ', Prompt Tokens: ' + str(usage.prompt_tokens))
        logging.info(f'##### End prompt #{id}\n')

        # Capture a summary of result for each prompt
        result = {
            'id': publication_id,
            'file_name': pdf_filepath.split(os.sep)[-1],
            'system_message': system_message,
            'prompt_id': index,
            'prompt': re.sub('\s+', ' ', prompt_template),
            'answer': re.sub('\s+', ' ', message.content),
            'variant': variant,
            'gene': gene,
            'expected_outcomes': expected_outcome,
            'prompt_tokens': usage.prompt_tokens,
            'completion_tokens': usage.completion_tokens,
            'estimated_cost': (0.01 * (usage.prompt_tokens/1000) + 0.03 * (usage.completion_tokens/1000)),
            'system_fingerprint': system_fingerprint,
            'timestamp': datetime.now().isoformat()
        }
        # Write the result to CSV file
        self.__write_result_to_csv(result)

        return result
    
    def __call_openapi_chat_completion(self, messages: List[Dict]) -> Dict:
        """
        Call GPT service to get a response back

        :param messages: GPT chat messages (history + new prompt)
        :return: response from GPT
        """
        if self.use_mock:
            # Enabled to use mock instead of calling GPT service
            # Useful when verifying the logic used before and after calling the service
            logging.debug('Calling mock service')       
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {
                            "content": "Evidence has found",
                            "role": "assistant"
                        }
                    }
                ],
                "created": 1679001781,
                "id": "chatcmpl-6upLpNYYOx2AhoOYxl9UgJvF4aPpR",
                "model": "gpt-3.5-turbo-0301",
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": 39,
                    "prompt_tokens": 58,
                    "total_tokens": 97
                }
            }
        else:
            logging.debug(f'Calling OpenAI: GPT Deployment - {self.gpt_deployment}')
            client = AzureOpenAI(
                azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
                api_key=os.getenv('AZURE_OPENAI_KEY'),  
                api_version=os.getenv('AZURE_OPENAI_VERSION')
                )
            return client.chat.completions.create(
                model=self.gpt_deployment,
                messages=messages,
                temperature=0,
                max_tokens=self.max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                seed=42
            )
        
    def __read_publication_configs(self, fname: str) -> Dict[str, Any]:
        """
        From the publication config file, get a list of functional paper to process
        along with their execusion parameters (e.g. variant, gene, aliases, etc.)
        """
        logging.debug('Reading publication param file: ' + fname)
        self.__validate_file_extension(fname, '.xlsx')

        data = read_excel(fname)

        pub_configs = {}
        for index, row in data.iterrows():
            publication = {
                'id': '',
                'file_path': '',
                'file_name': '',
                'variant': '',
                'gene': '',
                'variant_aliases': '',
                'expected_outcomes': ''
            }
            for key in data.keys():
                publication[key] = row[key]

            pub_id = publication['id']
            del publication['id']
            pub_configs[pub_id] = publication
        
        return pub_configs
    
    def __read_question_configs(self, file_path: str) -> Dict:
        """
        From the question config file, get a system message
        and a list of questions to execute.
        """
        logging.debug('Reading question config file: ' + file_path)
        self.__validate_file_extension(file_path, '.json')

        data = None
        with open(file_path, "r") as fd:
            data = json.load(fd)

        return data
    
    def __validate_file_extension(self, file_path: str, expected_ext: str) -> None:
        """
        Validates if the file in the given file path has the expected file extension

        If validation fails, throws a type error.
        """
        file_ext = pathlib.Path(file_path).suffix
        if file_ext != expected_ext: 
            raise TypeError(f"Only supports extension '{expected_ext}', but provided a file with '{file_ext}'")
    
    def __setup_result_file(self) -> str:
        """
        Creates a CSV file to store prompt execution results

        :return: path to the CSV file created
        """
        time_suffix = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")
        file_name = f'prompt_execution_result-{time_suffix}.csv'
        file_path = os.path.join('result', file_name)
        logging.debug('Setup result file: ' + file_path)

        file_exists = os.path.isfile(file_path)
        with open(file_path, mode='a') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            if not file_exists:
                writer.writeheader()

        return file_path
    
    def __write_result_to_csv(self, result: Dict) -> None:
        """
        Saves the given result to the CSV file set up during initialization
        """
        with open(self.result_file_path, mode='a') as csv_file:
            result_writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            result_writer.writerow(result)
            csv_file.close()


def main():
    parser = argparse.ArgumentParser(
        description='Execute prompts with aliases for genomics analysis')
    parser.add_argument(
        '--publicationId', help='Id of the publication to process', required=False, type=str)
    parser.add_argument(
        '--sleepAtEachPublication', help='If specified, wait x number of seconds before processing the next publication', required=False, type=int)
    parser.add_argument(
        '--useMock', help='Indicates whether or not to use a mock service instead of calling OpenAI', action='store_true')
    parser.add_argument(
        '--debug', help='Sets logger level to DEBUG', action='store_true')
    parser.add_argument(
        '--fileConfig', help='List of files to process', required=True)
    parser.add_argument(
        '--questionConfig', help='System message and list of questions', required=True)
    parser.add_argument(
        '--temperature', help='GPT model - temperature setting', required=False, type=int, default=0)
    parser.add_argument(
        '--maxTokens', help='GPT model - max # of tokens in response', required=False, type=int, default=1000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        handlers=[
                            TimedRotatingFileHandler(os.path.join('logs', 'execute_prompts.log'), when='midnight'),
                            logging.StreamHandler()
                        ])

    # Load environment variables
    load_dotenv()
    gpt_deployment = os.getenv('AZURE_GPT_DEPLOYMENT')
    logging.info(f'Endpoint: {os.getenv("AZURE_OPENAI_ENDPOINT")}')
    logging.info(f'Deployment: {gpt_deployment}')

    try:
        executor = PromptExecutor(args, gpt_deployment)
        executor.process()
    except Exception as ex:
        logging.error(ex, stack_info=True, exc_info=True)
        sys.exit('Caught an Exception with the following error message: {}\nExiting.'.format(ex))


if __name__ == "__main__":
    main()

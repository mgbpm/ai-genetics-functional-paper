import argparse
import csv
import logging
import os
import pathlib
import re
import sys
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from string import Template
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from pandas import read_excel

from utils import file_utils, variant_utils, prompt_utils

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

NODE_START = 'START'


class PromptExecutor:
    def __init__(self, args, gpt_deployment: str):
        self.publication_id: str = args.publicationId
        self.sleep_at_each_publication: int = args.sleepAtEachPublication
        self.publications_parameters: Dict[str, Any] = self.__read_publication_configs(args.fileConfig)
        self.questions_parameters: Dict = self.__read_question_configs(args.questionConfig)
        self.result_file_path: str = self.__setup_result_file()
        self.gpt_deployment: str = gpt_deployment
        self.temperature: float = args.temperature
        self.seed: int = args.seed
        self.max_tokens: int = args.maxTokens
        self.enable_json_mode: bool = args.enableJsonMode

    def process(self) -> None:
        """
        Process publications in PDF as per configuration
        """
        if self.publication_id:
            # Only process the publication specified in the argument
            self.__handle_single_publication(self.publication_id)
        else:
            # Process all files included in the specified folder
            count = 0
            for param in self.publications_parameters:
                self.__handle_single_publication(param)
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
            file_path = str(os.path.join(publication['file_path'], publication['file_name']))
            variant = publication['variant']
            gene = publication['gene']
            variant_aliases = publication['variant_aliases']
            variants_parsed = [s.strip() for s in variant_aliases.split(',')]
            expected_outcome = publication['expected_outcomes']

            if file_path and variant and gene and Path(file_path).suffix == '.pdf':
                self.__execute_sequential_prompts(publication_id, file_path, variant, gene, variants_parsed,
                                                  expected_outcome)
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
        # Configure a set of variants to try
        variants_to_check = [variant, f'{gene} {variant}']
        if longest_variant and longest_variant not in variants_to_check:
            variants_to_check.insert(0, longest_variant)

        # Initialize with a system message
        system_message = self.questions_parameters[KEY_SYSMSG]
        if '$param' in system_message:
            system_message = Template(system_message).substitute(param_variant=variant, param_gene=gene,
                                                                 param_variant_aliases=", ".join(variant_aliases))

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
            'param_gene': gene,
            'content': pdf_in_text,
            'publication_id': publication_id,
            'pdf_filepath': pdf_filepath,
            'system_message': system_message,
            'expected_outcome': expected_outcome
        }

        # Confirm that the starting point exists in the set of questions
        if not prompt_utils.has_node(questions, NODE_START):
            error_msg = f"Node '{NODE_START}' does not exist"
            logging.error(error_msg)
            raise prompt_utils.NodeMissingError(error_msg)

        # Check for a cycle in the set of questions defined to prevent infinite execution
        if prompt_utils.has_cycle(questions, NODE_START):
            error_msg = f"Cycle detected in the questions graph with the entry point at '{NODE_START}'"
            logging.error(error_msg)
            raise prompt_utils.CycleDetectedError(error_msg)

        for index, current_variant in enumerate(variants_to_check):
            logging.info(f'Attempt: {index + 1} - Processing with variant {current_variant}')
            last_question_processed_id = self.__process_with_variant(questions, current_variant, messages, input_params)
            # Current variant is present in the publication
            # and no longer need to check the other variant nomenclatures
            if last_question_processed_id != NODE_START:
                break

    def __process_with_variant(
            self,
            questions: Dict,
            variant: str,
            messages: List[Dict],
            input_params: Dict) -> str:
        previous_question_id = None
        current_question_id = NODE_START
        while current_question_id:
            logging.info(f"Current question ID: {current_question_id}")
            question = {
                KEY_QUESTION_ID: current_question_id,
                KEY_QUESTION: questions[current_question_id][KEY_QUESTION]
            }
            logging.info(f"Question: {question}")
            result = self.__execute_single_prompt(question, variant, messages, input_params)
            answer = result['answer']

            previous_question_id = current_question_id
            current_question_id = prompt_utils.get_next_question(questions, current_question_id, answer)

        return previous_question_id

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
        gene = input_params['param_gene']
        pdf_in_text = input_params['content']
        publication_id = input_params['publication_id']
        pdf_filepath = input_params['pdf_filepath']
        system_message = input_params['system_message']
        expected_outcome = input_params['expected_outcome']

        prompt_template = question[KEY_QUESTION]
        question_id = question[KEY_QUESTION_ID]
        logging.info(f'##### Start prompt #{question_id}')

        # Set up the next prompt
        prompt = Template(prompt_template).substitute(param_variant=variant, param_gene=gene, content=pdf_in_text)
        messages.append({
            "role": "user",
            "content": prompt
        })
        size_limit = min(len(messages[-1]['content']), 300)
        logging.info('> Human: ' + re.sub(r'\s+', ' ', messages[-1]['content'][:size_limit]) + ' ...')

        # Call OpenAI
        response = self.__call_openapi_chat_completion(messages)

        # Append response to the messages to retain previous context
        usage = response.usage
        system_fingerprint = response.system_fingerprint
        message = response.choices[0].message
        messages.append(message)
        logging.info('> AI: ' + message.content)
        logging.info(
            'Completion Tokens: ' + str(usage.completion_tokens) + ', Prompt Tokens: ' + str(usage.prompt_tokens))
        logging.info(f'##### End prompt #{question_id}\n')

        # Capture a summary of result for each prompt
        result = {
            'id': publication_id,
            'file_name': pdf_filepath.split(os.sep)[-1],
            'system_message': system_message,
            'prompt_id': question_id,
            'prompt': re.sub(r'\s+', ' ', prompt_template),
            'answer': re.sub(r'\s+', ' ', message.content),
            'variant': variant,
            'gene': gene,
            'expected_outcomes': expected_outcome,
            'prompt_tokens': usage.prompt_tokens,
            'completion_tokens': usage.completion_tokens,
            'estimated_cost': (0.01 * (usage.prompt_tokens / 1000) + 0.03 * (usage.completion_tokens / 1000)),
            'system_fingerprint': system_fingerprint,
            'timestamp': datetime.now().isoformat()
        }
        # Write the result to CSV file
        self.__write_result_to_csv(result)

        return result

    def __call_openapi_chat_completion(self, messages: List[Dict]) -> ChatCompletion:
        """
        Call GPT service to get a response back

        :param messages: GPT chat messages (history + new prompt)
        :return: response from GPT
        """
        logging.debug(f'Calling OpenAI: GPT Deployment - {self.gpt_deployment}')
        client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv('AZURE_OPENAI_KEY'),
            api_version=os.getenv('AZURE_OPENAI_VERSION')
        )

        # Handles JSON mode
        response_format = {"type": "json_object"} if self.enable_json_mode else None
        return client.chat.completions.create(
            model=self.gpt_deployment,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            seed=self.seed,
            response_format=response_format
        )

    def __read_publication_configs(self, file_path: str) -> Dict[str, Any]:
        """
        From the publication config file, get a list of functional paper to process
        along with their execution parameters (e.g. variant, gene, aliases, etc.)
        """
        logging.debug('Reading publication param file: ' + file_path)
        self.__validate_file_extension(file_path, '.xlsx')

        data = read_excel(file_path)

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

        return prompt_utils.load_questions_config(file_path)

    @staticmethod
    def __validate_file_extension(file_path: str, expected_ext: str) -> None:
        """
        Validates if the file in the given file path has the expected file extension

        If validation fails, throws a type error.
        """
        file_ext = pathlib.Path(file_path).suffix
        if file_ext != expected_ext:
            raise TypeError(f"Only supports extension '{expected_ext}', but provided a file with '{file_ext}'")

    @staticmethod
    def __setup_result_file() -> str:
        """
        Creates a CSV file to store prompt execution results

        :return: path to the CSV file created
        """
        time_suffix = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")
        file_name = f'prompt_execution2_result-{time_suffix}.csv'
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
        '--sleepAtEachPublication',
        help='If specified, wait x number of seconds before processing the next publication', required=False, type=int)
    parser.add_argument(
        '--debug', help='Sets logger level to DEBUG', action='store_true')
    parser.add_argument(
        '--fileConfig', help='List of files to process', required=True)
    parser.add_argument(
        '--questionConfig', help='System message and list of questions', required=True)
    parser.add_argument(
        '--temperature', help='GPT model - temperature setting', required=False, type=float, default=0)
    parser.add_argument(
        '--seed', help='GPT model - seed setting', required=False, type=int, default=42)
    parser.add_argument(
        '--maxTokens', help='GPT model - max # of tokens in response', required=False, type=int, default=1000)
    parser.add_argument(
        '--enableJsonMode', help='GPT model - JSON mode', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        handlers=[
                            TimedRotatingFileHandler(os.path.join('logs', 'execute_prompts2.log'), when='midnight'),
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

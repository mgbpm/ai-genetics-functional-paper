import json
import requests

# Instructions:
#
# These functions produce lists of nomenclature variations given a genome build, gene, transcript, cdna change and aa change
# If no cdna change is provided the function will return variations of the aa change only.
#
# Usage:
# build, gene, transcript, cdna, aachange = "GRCh38", "MYH7", "NM_000257.4", "c.630C>G", "p.S210R"
# output = get_nomenclature_variations(build, gene, transcript, cdna, aachange)
# print(output)
#
# {'630C/G', 'MYH7 c.630C>G', 'p.S210R', 'Ser210Arg', 'p.(Ser210Arg)', 'S210R', 'LRG_384p1:p.(S210R)', 'p.Ser210Arg', 'p.(S210R)', 'NC_000014.8:g.23900979G>C', '630C>G', 'c.630C/G', 'MYH7 c.630C>G (p.Ser210Arg)', 'NP_000248.2:p.(Ser210Arg)', 'NC_000014.9:g.23431770G>C', 'c.630C>G', 'NM_000257.4:c.630C>G', '(Ser210Arg)', '(S210R)', 'NP_000248.2:p.(S210R)', 'LRG_384p1:p.(Ser210Arg)'}
#
# This library could be called as part of an automated pipeline, but for our study we created a spread sheet containing these variables
# and then manually created the output and pasted the results back to the spreadsheet for access by the GPT-4 script.

# amino acid long and short forms
longToShort = {
    'Ala': 'A',
    'Arg': 'R',
    'Asn': 'N',
    'Asp': 'D',
    'Asx': 'B',
    'Cys': 'C',
    'Gln': 'Q',
    'Glu': 'E',
    'Glx': 'Z',
    'Gly': 'G',
    'His': 'H',
    'Ile': 'I',
    'Leu': 'L',
    'Lys': 'K',
    'Met': 'M',
    'Phe': 'F',
    'Pro': 'P',
    'Ser': 'S',
    'Thr': 'T',
    'Trp': 'W',
    'Tyr': 'Y',
    'Val': 'V',
    'Ter': 'X',
    '*': 'X',
    'X': '*'
}

shortToLong = {
    'A': 'Ala',
    'R': 'Arg',
    'N': 'Asn',
    'D': 'Asp',
    'B': 'Asx',
    'C': 'Cys',
    'Q': 'Gln',
    'E': 'Glu',
    'Z': 'Glx',
    'G': 'Gly',
    'H': 'His',
    'I': 'Ile',
    'L': 'Leu',
    'K': 'Lys',
    'M': 'Met',
    'F': 'Phe',
    'P': 'Pro',
    'S': 'Ser',
    'T': 'Thr',
    'W': 'Trp',
    'Y': 'Tyr',
    'V': 'Val',
    '*': 'Ter',
    'X': 'Ter',
}

# assumes input of p.A123B or p.Abc123Def format, returns list of aa variations
def get_nomenclature_variations_aa(aa_change):
    # set to return
    variations = set()

    # add original as submitted
    variations.add(aa_change)

    # add without "p."
    aa_nopdot = aa_change.replace("p.","")
    variations.add(aa_nopdot)

    # add with parens
    aa_parens = "(" + aa_nopdot + ")"
    variations.add(aa_parens)

    # add with "p." and parens
    aa_pdotparens = "p." + aa_parens
    variations.add(aa_pdotparens)

    # deterine if short or long format (p.A123B or p.Abc123Def)
    aa_long_first = next((x for x in longToShort.keys() if x in aa_change), None)
    if aa_long_first == None:  # Must be short form
        # add long aa form
        aa_short_first = next((x for x in shortToLong.keys() if x in aa_change), None)
        aa_short_second = next((x for x in shortToLong.keys() if x in aa_change.replace(aa_short_first,"Z")), None)
        long_aa = aa_change.replace(aa_short_first,shortToLong[aa_short_first]).replace(aa_short_second,shortToLong[aa_short_second])
        variations.add(long_aa)

        # add long aa without "p."
        long_aa_nopdot = long_aa.replace("p.","")
        variations.add(long_aa_nopdot)

        # add long aa with parens
        long_aa_parens = "(" + long_aa_nopdot + ")"
        variations.add(long_aa_parens)

        # add long aa with "p." and parens
        long_aa_pdotparens = "p." + long_aa_parens
        variations.add(long_aa_pdotparens)

    else:  # Must be long form
        # add short aa form
        aa_long_second = next((x for x in longToShort.keys() if x in aa_change.replace(aa_long_first,"ZZZ")), None)
        short_aa = aa_change.replace(aa_long_first, longToShort[aa_long_first]).replace(aa_long_second,longToShort[aa_long_second])
        variations.add(short_aa)

        # add short without "p."
        short_aa_nopdot = short_aa.replace("p.", "")
        variations.add(short_aa_nopdot)

        # add short with parens
        short_aa_parens = "(" + short_aa_nopdot + ")"
        variations.add(short_aa_parens)

        # add short with "p." and parens
        short_aa_pdotparens = "p." + short_aa_parens
        variations.add(short_aa_pdotparens)

    return variations

# with input of genome build, gene transcript and cdna change, returns list of cdna variations
def get_nomenclature_variations_cdna(build, transcript, cdna):
    # set to return
    global lrg_tlr_aa_noparen
    variations = set()

    # get variant info from Variant Validator API
    req = "https://rest.variantvalidator.org/VariantValidator/variantvalidator/"+build+"/"+transcript+":"+cdna+"/all?content-type=application/json"
    print(req)
    resp = requests.get(req)
    resp_dict = resp.json()
    json_data = json.loads(resp.text)
    root = list(resp_dict.keys())[0]
    data = resp_dict[root]

    # get the gene symbol from api response
    gene = data.get("gene_symbol")

    # various amino acid changes
    aachanges = data.get("hgvs_predicted_protein_consequence")
    lrg_slr = aachanges.get("lrg_slr") # "LRG_274p1:p.(M1?)"
    if len(lrg_slr) > 0:
        variations.add(lrg_slr)
        # p.(M1?)
        lrg_slr_aa =lrg_slr.split(":",1)[1]
        variations.add(lrg_slr_aa)
        # (M1?)
        lrg_slr_aa_nopdot = lrg_slr_aa.replace("p.","",1)
        variations.add(lrg_slr_aa_nopdot)
        # p.M1?
        lrg_slr_aa_noparen = lrg_slr_aa.replace("(","").replace(")","")
        variations.add(lrg_slr_aa_noparen)
        # M1?
        lrg_slr_aa_nopdotparen = lrg_slr_aa_noparen.replace("p.","")
        variations.add(lrg_slr_aa_nopdotparen)
    # LRG_274p1:p.(Met1?)
    lrg_tlr = aachanges.get("lrg_tlr") # "LRG_274p1:p.(Met1?)"
    if len(lrg_tlr) > 0:
        variations.add(lrg_tlr)
        # p.(Met1?)
        lrg_tlr_aa = lrg_tlr.split(":",1)[1]
        variations.add(lrg_tlr_aa)
        # p.Met1?
        lrg_tlr_aa_noparen = lrg_tlr_aa.replace("(","").replace(")","")
        variations.add(lrg_tlr_aa_noparen)
        # (Met1?)
        lrg_tlr_aa_nopdot = lrg_tlr_aa.replace("p.","")
        variations.add(lrg_tlr_aa_nopdot)
        # Met1?
        lrg_tlr_aa_nopdotparen = lrg_tlr_aa_nopdot.replace("(","").replace(")","")
        variations.add(lrg_tlr_aa_nopdotparen)
    # p.(M1?)
    slr = aachanges.get("slr") # "NP_000518.1:p.(M1?)"
    variations.add(slr)
    # p.(Met1?)
    tlr = aachanges.get("tlr") # "NP_000518.1:p.(Met1?)"
    variations.add(tlr)
    # "NM_000527.5:c.1A>C",
    hgvs_transcript_variant = data.get("hgvs_transcript_variant")
    variations.add(hgvs_transcript_variant)
    # c.1A>G
    cdna_std = hgvs_transcript_variant.split(":",1)[1]
    variations.add(cdna_std)
    # 1A>G
    cdna_base = cdna_std.split(".",1)[1]
    variations.add(cdna_base)
    # c.1A/G
    cdna_std_slash = cdna_std.replace(">","/")
    variations.add(cdna_std_slash)
    # 1A/G
    cdna_base_slash = cdna_base.replace(">","/")
    variations.add(cdna_base_slash)

    # genomic variant nomenclature on builds 37 & 38
    genomic_vars = data.get("primary_assembly_loci")
    # NC_000017.10:g.41276044A>G
    build37 = genomic_vars.get("grch37")["hgvs_genomic_description"]
    variations.add(build37)
    # NC_000017.11:g.43124027A>G
    build38 = genomic_vars.get("grch38")["hgvs_genomic_description"]
    variations.add(build38)

    # combinations
    variations.add(gene+" "+cdna)
    if len(lrg_tlr_aa_noparen) > 0:
        variations.add(gene+" "+cdna+" ("+lrg_tlr_aa_noparen+")")
    return variations


def get_nomenclature_variations(build, gene, transcript, cdna, aa_change):

    if cdna == "":
        variations = get_nomenclature_variations_aa(aa_change)
        variations.add(aa_change + " (" + gene + ")")
        return variations
    else:
        variations = get_nomenclature_variations_cdna(build, transcript, cdna)
        return variations

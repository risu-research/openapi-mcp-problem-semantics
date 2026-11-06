"""P4-Q mutation tests operating on the real, original JPO VCR -> MCP replay.

Requires the pinned external project VCR replay from the P4-N/P4-P workflow.
No tests execute third-party code; only mutate copied in-memory records.
"""
import copy
import json
import unittest
from pathlib import Path

from risu_arraymatch import assess_arrays

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parent
RUN=ROOT/"p4n"/"results"
MAP=HERE/"jpo_arrays.json"

def pair():
    har=json.loads((RUN/"risu_native_inputs"/"normal"/"capture.har").read_text())
    body=json.loads(har["log"]["entries"][0]["response"]["content"]["text"])
    output=json.loads((RUN/"normal"/"case_report.json").read_text())
    return {"cases":[{"id":"JPO_normal","source":{"status":200,"body":body},"mcp":output["mcp_call_result"]}]}

def evaluate(case):
    return assess_arrays(case,MAP,RUN/"risu_native_inputs"/"normal")

def get_state(result,name):
    return next(x for x in result["cases"][0]["groups"] if x["id"]==name)

class OriginalJPOWireKeyedArrayTests(unittest.TestCase):
    def setUp(self):
        self.case=pair()
        self.src=self.case["cases"][0]["source"]["body"]["result"]["data"]
        self.tar=self.case["cases"][0]["mcp"]["structuredContent"]["items"][0]
    def test_original_witnessed_three_groups(self):
        x=evaluate(self.case)["summary"]
        self.assertEqual((x["matched_groups"],x["matched_rows"],x["candidate_exact_leaf_units"]),(3,14,118))
    def test_original_expected_cardinalities(self):
        self.assertEqual(len(self.src["applicantAttorney"]),1)
        self.assertEqual([len(x["documentList"]) for x in self.src["bibliographyInformation"]],[6,5])
    def test_keyed_document_permutation_allowed(self):
        self.tar["bibliography_information"].reverse()
        for row in self.tar["bibliography_information"]:row["document_list"].reverse()
        self.assertEqual(evaluate(self.case)["summary"]["candidate_exact_leaf_units"],118)
    def test_deletion_detected(self):
        self.tar["bibliography_information"][0]["document_list"].pop()
        self.assertEqual(get_state(evaluate(self.case),"document_list")["reason"],"ARRAY_CARDINALITY_DIFFERENT")
    def test_insertion_detected(self):
        row=copy.deepcopy(self.tar["bibliography_information"][0]["document_list"][0])
        row["document_number"]="extra-record"
        self.tar["bibliography_information"][0]["document_list"].append(row)
        self.assertEqual(get_state(evaluate(self.case),"document_list")["status"],"CONTRADICTED")
    def test_description_value_changed_detected(self):
        self.tar["bibliography_information"][0]["document_list"][0]["document_description"]="changed"
        self.assertEqual(get_state(evaluate(self.case),"document_list")["reason"],"MISMATCHED_ROW_FIELD_VALUE_OR_TYPE")
    def test_only_document_number_is_ambiguous(self):
        self.assertGreater(sum(x["documentNumber"]=="99999999999" for x in self.src["bibliographyInformation"][1]["documentList"]),2)
        mapping=json.loads(MAP.read_text())
        mapping["cases"][0]["groups"][2]["identity"]=["documentNumber"]
        # Different map must be independently operator-selected, never edited inside capture folder.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            selected=Path(d)/"bad.json"
            selected.write_text(json.dumps(mapping))
            x=assess_arrays(self.case,selected,RUN/"risu_native_inputs"/"normal")
            self.assertEqual(get_state(x,"document_list")["reason"],"DUPLICATE_OR_AMBIGUOUS_SOURCE_IDENTITY")
    def test_duplicated_composite_key_detected(self):
        docs=self.tar["bibliography_information"][0]["document_list"]
        for field in ("document_number","document_code","legal_date"):docs[1][field]=docs[0][field]
        self.assertEqual(get_state(evaluate(self.case),"document_list")["reason"],"DUPLICATE_OR_AMBIGUOUS_TARGET_IDENTITY")
    def test_untrusted_row_reparented_detected(self):
        a=self.tar["bibliography_information"][0]["document_list"]
        b=self.tar["bibliography_information"][1]["document_list"]
        a[0],b[0]=b[0],a[0]
        self.assertEqual(get_state(evaluate(self.case),"document_list")["status"],"CONTRADICTED")
    def test_false_type_transform_rejected(self):
        self.tar["bibliography_information"][0]["document_list"][0]["number_of_pages"]=0
        self.assertEqual(get_state(evaluate(self.case),"document_list")["status"],"CONTRADICTED")
    def test_missing_machine_structured_data_is_insufficient(self):
        self.case["cases"][0]["mcp"].pop("structuredContent")
        self.assertEqual(get_state(evaluate(self.case),"applicant_attorney")["status"],"INSUFFICIENT")
    def test_no_source_values_are_exported_by_extension(self):
        obj=evaluate(self.case)
        s=json.dumps(obj)
        for sentinel in ("99999999999","2020015234","22011160009"):
            self.assertNotIn(sentinel,s)
    def test_missing_scalar_field_rejected(self):
        self.tar["bibliography_information"][0]["document_list"][0].pop("irir_flg")
        self.assertEqual(get_state(evaluate(self.case),"document_list")["reason"],"TARGET_COLUMN_SHAPE_DISAGREEMENT")
    def test_field_modified_under_same_id_rejected(self):
        self.tar["applicant_attorney"][0]["name"]="wrong person"
        self.assertEqual(get_state(evaluate(self.case),"applicant_attorney")["status"],"CONTRADICTED")

if __name__=="__main__":unittest.main()

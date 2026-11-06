"""P4-V adversarial nested-schema obligations and provenance tests."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import unittest
from risu_nested_schema import SchemaLens, compare

HERE=Path(__file__).resolve().parents[2]
CAP=Path(os.environ.get('P4V_CAPTURES_DIR',str(HERE/'p4u'/'results')))

def schema(ver,tool='convert_time'):
    return next(x['outputSchema'] for x in json.loads((CAP/ver/'tools_list.json').read_text())['result']['tools'] if x['name']==tool)

class TestActualExternalReleases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=schema('2026.10.19');cls.new=schema('2026.11.4')

    def test_original_external_schemas_are_different(self):
        self.assertNotEqual(self.old,self.new)
    def test_original_ref_properties_old(self):
        d=SchemaLens(self.old).scan()
        self.assertEqual(d['field_count'],11)
        self.assertTrue(d['fields']['/source/timezone']['unconditionally_required'])
        self.assertTrue(d['fields']['/target/is_dst']['unconditionally_required'])
        self.assertEqual(d['fields']['/source/timezone']['types'],['string'])
        self.assertEqual(d['fields']['/source/is_dst']['types'],['boolean'])
    def test_exact_field_counts(self):
        d=compare(self.old,self.new)
        self.assertEqual(d['new']['field_count'],24)
        self.assertEqual(d['summary']['independent_events'],1)
        self.assertEqual(d['summary']['conditional_detail_events'],13)
    def test_parent_optional_unconditional_zero(self):
        d=compare(self.old,self.new)
        self.assertEqual(d['summary']['unconditionally_required_new_fields'],0)
        self.assertEqual(d['events'][0]['path'],'/later_occurrence')
        self.assertEqual(d['events'][0]['after']['types'],['null','object'])
        self.assertFalse(d['events'][0]['after']['required_local'])
    def test_ref_descendants_are_guarded(self):
        d=SchemaLens(self.new).scan()['fields']
        for path in ('/later_occurrence/@anyOf[type:object]/note','/later_occurrence/@anyOf[type:object]/source/timezone','/later_occurrence/@anyOf[type:object]/target/timezone','/later_occurrence/@anyOf[type:object]/time_difference'):
            self.assertTrue(d[path]['required_local'])
            self.assertFalse(d[path]['unconditionally_required'])
            self.assertTrue(d[path]['guard'])
    def test_no_fake_changed_original_required_ref_fields(self):
        d=compare(self.old,self.new)
        self.assertFalse(any(x['path'].startswith('/source/') or x['path'].startswith('/target/') for x in d['events']))
    def test_union_reorder_no_diff(self):
        new=copy.deepcopy(self.new)
        new['properties']['later_occurrence']['anyOf'].reverse()
        self.assertEqual(compare(self.new,new)['summary']['independent_events'],0)
        self.assertEqual(compare(self.new,new)['summary']['conditional_detail_events'],0)
    def test_unreferenced_defs_do_not_create_output_issues(self):
        new=copy.deepcopy(self.old)
        new['$defs']['Unused']={'type':'object','properties':{'secret':{'type':'string'}},'required':['secret']}
        self.assertEqual(compare(self.old,new)['summary']['independent_events'],0)
    def test_rename_ref_target_equivalent(self):
        new=copy.deepcopy(self.old)
        new['$defs']['RenamedTimeResult']=new['$defs'].pop('TimeResult')
        for x in ('source','target'):new['properties'][x]['$ref']='#/$defs/RenamedTimeResult'
        self.assertEqual(compare(self.old,new)['summary']['independent_events'],0)
    def test_actual_ref_target_type_drift(self):
        new=copy.deepcopy(self.old)
        new['$defs']['TimeResult']['properties']['is_dst']['type']='string'
        events=compare(self.old,new)['events']
        self.assertEqual([x['path'] for x in events],['/source/is_dst','/target/is_dst'])
        self.assertTrue(all(x['kind']=='TYPE_SET_CHANGED' for x in events))
    def test_nested_required_to_optional(self):
        new=copy.deepcopy(self.old)
        new['$defs']['TimeResult']['required'].remove('timezone')
        events=compare(self.old,new)['events']
        self.assertEqual([(x['kind'],x['path']) for x in events],
           [('REQUIRED_TO_OPTIONAL','/source/timezone'),('REQUIRED_TO_OPTIONAL','/target/timezone')])
    def test_new_optional_to_required_top_level(self):
        new=copy.deepcopy(self.new)
        new['required'].append('later_occurrence')
        d=compare(self.new,new)
        self.assertEqual(d['events'][0]['kind'],'OPTIONAL_TO_REQUIRED')
        self.assertEqual(d['events'][0]['risk'],'REVIEW_REQUIRED')
        self.assertFalse(SchemaLens(new).scan()['fields']['/later_occurrence/@anyOf[type:object]/note']['unconditionally_required'])
    def test_new_non_nullable_branch_might_affect_downstream(self):
        new=copy.deepcopy(self.new)
        new['properties']['later_occurrence']['anyOf']=[new['properties']['later_occurrence']['anyOf'][0]]
        d=compare(self.new,new)
        self.assertEqual(d['events'][0]['kind'],'TYPE_SET_NARROWED')
        self.assertEqual(d['summary']['potential_compatibility_changes'],1)
        self.assertEqual(d['union_events'][0]['kind'],'UNION_ALTERNATIVES_CHANGED')
    def test_nested_type_widening(self):
        new=copy.deepcopy(self.old)
        new['$defs']['TimeResult']['properties']['datetime']['type']=['string','null']
        events=compare(self.old,new)['events']
        self.assertEqual([x['kind'] for x in events],['TYPE_SET_WIDENED','TYPE_SET_WIDENED'])
    def test_no_mutation_of_input(self):
        x=copy.deepcopy(self.new)
        SchemaLens(self.new).scan()
        self.assertEqual(x,self.new)

class TestFailClosed(unittest.TestCase):
    def test_unresolved_local_ref(self):
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            SchemaLens({'type':'object','properties':{'x':{'$ref':'#/$defs/Unseen'}}}).scan()
    def test_remote_ref(self):
        with self.assertRaisesRegex(ValueError,'External'):
            SchemaLens({'type':'object','properties':{'x':{'$ref':'https://example.org/Schema'}}}).scan()
    def test_cyclic_ref(self):
        x={'type':'object','$defs':{'Loop':{'type':'object','properties':{'next':{'$ref':'#/$defs/Loop'}}}},'properties':{'root':{'$ref':'#/$defs/Loop'}}}
        with self.assertRaisesRegex(ValueError,'Cyclic'):
            SchemaLens(x).scan()
    def test_ambiguous_branch_objects(self):
        x={'type':'object','properties':{'x':{'anyOf':[{'type':'object','properties':{'a':{'type':'string'}}},{'type':'object','properties':{'b':{'type':'boolean'}}}]}}}
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            SchemaLens(x).scan()
    def test_duplicate_required(self):
        x={'type':'object','properties':{'a':{'type':'string'}},'required':['a','a']}
        with self.assertRaisesRegex(ValueError,'duplicate|duplicated'):
            SchemaLens(x).scan()
    def test_nonexistent_required(self):
        with self.assertRaises(ValueError):SchemaLens({'type':'object','required':['x']}).scan()
    def test_union_duplicate_type(self):
        with self.assertRaises(ValueError):SchemaLens({'properties':{'x':{'anyOf':[{'type':'null'},{'type':'null'}]}}}).scan()
    def test_ref_with_constrained_sibling(self):
        x={'$defs':{'T':{'type':'string'}},'properties':{'a':{'$ref':'#/$defs/T','minLength':2}}}
        with self.assertRaisesRegex(ValueError,'sibling'):
            SchemaLens(x).scan()
    def test_allof_review_boundary(self):
        x={'properties':{'x':{'allOf':[{'type':'string'}]}}}
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            SchemaLens(x).scan()
    def test_if_then_review_boundary(self):
        x={'properties':{'x':{'if':{'type':'object'},'then':{'required':['a']}}}}
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            SchemaLens(x).scan()
    def test_invalid_type_list(self):
        with self.assertRaises(ValueError):SchemaLens({'properties':{'x':{'type':['string','string']}}}).scan()
    def test_array_items_nested(self):
        x={'type':'object','properties':{'rows':{'type':'array','items':{'type':'object','properties':{'id':{'type':'string'}},'required':['id']}}},'required':['rows']}
        d=SchemaLens(x).scan()['fields']
        self.assertIn('/rows/@items/id',d)
        self.assertFalse(d['/rows/@items/id']['unconditionally_required'])
    def test_json_pointer_escaping(self):
        x={'$defs':{'A/B':{'type':'object','properties':{'a/b~c':{'type':'string'}}}},'properties':{'x':{'$ref':'#/$defs/A~1B'}}}
        self.assertIn('/x/a~1b~0c',SchemaLens(x).scan()['fields'])
    def test_too_deep_review(self):
        d={'type':'string'}
        for _ in range(40):d={'type':'object','properties':{'next':d}}
        with self.assertRaisesRegex(ValueError,'depth|complex'):
            SchemaLens(d).scan()
    def test_unsupported_prefix_schema_safely(self):
        # Old P4-T cannot see prefixItems. P4-V needs to explicitly refuse instead of treating as no change.
        x={'type':'array','prefixItems':[{'type':'string'}]}
        with self.assertRaises(ValueError):SchemaLens(x).scan()

if __name__=='__main__':unittest.main()

class TestValidationConstraints(unittest.TestCase):
    def test_deeper_min_length_changed(self):
        original={'type':'object','$defs':{'X':{'type':'object','properties':{'id':{'type':'string','minLength':2}},'required':['id']}},'properties':{'payload':{'$ref':'#/$defs/X'}},'required':['payload']}
        modified=copy.deepcopy(original)
        modified['$defs']['X']['properties']['id']['minLength']=4
        result=compare(original,modified)
        self.assertEqual([(e['kind'],e['path']) for e in result['events']],[('VALIDATION_CONSTRAINT_CHANGED_REVIEW','/payload/id')])
    def test_description_title_default_are_not_mandatory_change(self):
        original={'type':'object','properties':{'x':{'type':'string','description':'old','title':'Title','default':'a'}}}
        modified=copy.deepcopy(original);modified['properties']['x'].update({'description':'new','title':'Other','default':'b'})
        self.assertEqual(compare(original,modified)['summary']['independent_events'],0)
    def test_additional_properties_boolean_changed(self):
        old={'type':'object','properties':{'x':{'type':'object','additionalProperties':False}}}
        new=copy.deepcopy(old);new['properties']['x']['additionalProperties']=True
        self.assertEqual(compare(old,new)['events'][0]['kind'],'VALIDATION_CONSTRAINT_CHANGED_REVIEW')
    def test_unsupported_arbitrary_keyword_is_review_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError,'Unknown semantic constraint'):
            SchemaLens({'type':'object','properties':{'x':{'type':'string','minGarbage':2}}}).scan()
    def test_untyped_ref_target_with_properties(self):
        x={'$defs':{'X':{'properties':{'x':{'type':'string'}}}},'properties':{'a':{'$ref':'#/$defs/X'}}}
        self.assertIn('/a/x',SchemaLens(x).scan()['fields'])
    def test_validating_sibling_ref_annotation_does_not_change_behavior(self):
        x={'$defs':{'X':{'type':'string'}},'properties':{'a':{'$ref':'#/$defs/X','description':'some'}}}
        self.assertEqual(SchemaLens(x).scan()['fields']['/a']['types'],['string'])
    def test_unknown_root_constraint_fails(self):
        with self.assertRaises(ValueError):SchemaLens({'type':'object','unevaluatedProperties':False}).scan()

from unittest import TestCase

from RLTest.utils import fix_modulesArgs


class TestFixModulesArgs(TestCase):

    # 1. Single key-value pair string, no defaults - kept as single string
    def test_single_key_value_pair(self):
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4')
        self.assertEqual(result, [['WORKERS 4']])

    # 2. Multiple key-value pairs without semicolons, no defaults - kept as single string
    def test_multiple_kv_pairs_no_semicolons_no_defaults(self):
        result = fix_modulesArgs(['/mod.so'], '_FREE_RESOURCE_ON_THREAD FALSE TIMEOUT 80 WORKERS 4')
        self.assertEqual(result, [['_FREE_RESOURCE_ON_THREAD FALSE TIMEOUT 80 WORKERS 4']])

    # 3. Semicolon-separated args (existing behavior)
    def test_semicolon_separated_args(self):
        result = fix_modulesArgs(['/mod.so'], 'KEY1 V1; KEY2 V2')
        self.assertEqual(result, [['KEY1 V1', 'KEY2 V2']])

    # 4. Odd number of words without semicolons, no defaults - kept as single string, no error
    def test_odd_words_no_semicolons_no_error(self):
        result = fix_modulesArgs(['/mod.so'], 'FLAG TIMEOUT 80 ')
        self.assertEqual(result, [['FLAG TIMEOUT 80']])

    # 4b. Odd number of words with semicolons - valid, semicolons split first
    def test_odd_words_with_semicolons_valid(self):
        result = fix_modulesArgs(['/mod.so'], 'FLAG; TIMEOUT 80')
        self.assertEqual(result, [['FLAG', 'TIMEOUT 80']])

    # 5a. Plain string with defaults - word-based merge, missing defaults appended
    def test_plain_string_overrides_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60', 'EXTRA 1']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 TIMEOUT 80', defaults)
        # Result is a single merged string
        self.assertEqual(result, [['WORKERS 4 TIMEOUT 80 EXTRA 1']])

    # 5b. Semicolon-separated string overrides matching defaults (dict-based merge)
    def test_semicolon_separated_overrides_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60', 'EXTRA 1']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4; TIMEOUT 80', defaults)
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['WORKERS'], 'WORKERS 4')
        self.assertEqual(result_dict['TIMEOUT'], 'TIMEOUT 80')
        self.assertEqual(result_dict['EXTRA'], 'EXTRA 1')

    # 5c. Plain string partial override - missing defaults appended
    def test_plain_string_partial_override_with_defaults(self):
        defaults = [['_FREE_RESOURCE_ON_THREAD TRUE', 'TIMEOUT 100', 'WORKERS 8']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 TIMEOUT 80', defaults)
        self.assertEqual(result, [['WORKERS 4 TIMEOUT 80 _FREE_RESOURCE_ON_THREAD TRUE']])

    # 6. None input with defaults - deep copy of defaults
    def test_none_uses_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60']]
        result = fix_modulesArgs(['/mod.so'], None, defaults)
        self.assertEqual(result, defaults)
        # Verify it's a deep copy
        result[0][0] = 'MODIFIED'
        self.assertEqual(defaults[0][0], 'WORKERS 8')

    # 7. List of strings with defaults - dict-based merge
    def test_list_of_strings_with_defaults(self):
        defaults = [['K1 default1', 'K2 default2', 'K4 default4']]
        result = fix_modulesArgs(['/mod.so'], ['K1 override1', 'K2 override2', 'K3 new3'], defaults)
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['K1'], 'K1 override1')
        self.assertEqual(result_dict['K2'], 'K2 override2')
        self.assertEqual(result_dict['K3'], 'K3 new3')
        self.assertEqual(result_dict['K4'], 'K4 default4')

    # 8. List of lists (multi-module) with defaults - dict-based merge
    def test_multi_module_with_defaults(self):
        modules = ['/mod1.so', '/mod2.so']
        explicit = [['K1 v1', 'K2 v2'], ['K3 v3']]
        defaults = [['K1 d1', 'K5 d5'], ['K3 d3', 'K4 d4']]
        result = fix_modulesArgs(modules, explicit, defaults)
        dict1 = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(dict1['K1'], 'K1 v1')
        self.assertEqual(dict1['K2'], 'K2 v2')
        self.assertEqual(dict1['K5'], 'K5 d5')
        dict2 = {arg.split(' ')[0]: arg for arg in result[1]}
        self.assertEqual(dict2['K3'], 'K3 v3')
        self.assertEqual(dict2['K4'], 'K4 d4')

    # 9. Odd words with defaults - word-based merge, flags and multi-value args handled
    def test_odd_words_with_defaults(self):
        defaults = [['FORK_GC_CLEAN_NUMERIC_EMPTY_NODES', 'TIMEOUT 90']]
        result = fix_modulesArgs(['/mod.so'], 'workers 0 nogc FORK_GC_CLEAN_NUMERIC_EMPTY_NODES timeout 90', defaults)
        self.assertEqual(result, [['workers 0 nogc FORK_GC_CLEAN_NUMERIC_EMPTY_NODES timeout 90']])

    # 10. Plain string with defaults - unknown keys not in defaults stay, missing defaults appended
    def test_plain_string_new_keys_with_defaults(self):
        defaults = [['TIMEOUT 60']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 TIMEOUT 80', defaults)
        self.assertEqual(result, [['WORKERS 4 TIMEOUT 80']])

    # 11. Case-insensitive word matching for plain string merge
    def test_case_insensitive_word_merge(self):
        defaults = [['workers 8', 'TIMEOUT 60', 'EXTRA 1']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 timeout 80', defaults)
        self.assertEqual(result, [['WORKERS 4 timeout 80 EXTRA 1']])

    # 12. Substring key should not falsely match (GC should not match nogc)
    def test_no_substring_match(self):
        defaults = [['GC enabled']]
        result = fix_modulesArgs(['/mod.so'], 'nogc TIMEOUT 80', defaults)
        self.assertEqual(result, [['nogc TIMEOUT 80 GC enabled']])

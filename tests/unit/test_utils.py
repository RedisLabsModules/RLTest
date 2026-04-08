from unittest import TestCase

from RLTest.utils import fix_modulesArgs


class TestFixModulesArgs(TestCase):

    # 1. Single key-value pair string
    def test_single_key_value_pair(self):
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4')
        self.assertEqual(result, [['WORKERS 4']])

    # 2. Multiple key-value pairs without semicolons - kept as single string
    def test_multiple_kv_pairs_no_semicolons(self):
        result = fix_modulesArgs(['/mod.so'], '_FREE_RESOURCE_ON_THREAD FALSE TIMEOUT 80 WORKERS 4')
        self.assertEqual(result, [['_FREE_RESOURCE_ON_THREAD FALSE TIMEOUT 80 WORKERS 4']])

    # 3. Semicolon-separated args (existing behavior)
    def test_semicolon_separated_args(self):
        result = fix_modulesArgs(['/mod.so'], 'KEY1 V1; KEY2 V2')
        self.assertEqual(result, [['KEY1 V1', 'KEY2 V2']])

    # 4a. Odd number of words without semicolons - kept as single string (no error)
    def test_odd_words_no_semicolons_kept_as_single(self):
        result = fix_modulesArgs(['/mod.so'], 'FLAG TIMEOUT 80')
        self.assertEqual(result, [['FLAG TIMEOUT 80']])

    # 4b. Odd number of words with semicolons - valid, semicolons split first
    def test_odd_words_with_semicolons_valid(self):
        result = fix_modulesArgs(['/mod.so'], 'FLAG; TIMEOUT 80')
        self.assertEqual(result, [['FLAG', 'TIMEOUT 80']])

    # 5a. Space-separated string kept as single arg, non-matching defaults added
    def test_space_separated_overrides_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60', 'EXTRA 1']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 TIMEOUT 80', defaults)
        # Without semicolons, the string is kept as one arg (first word = WORKERS).
        # Only 'WORKERS 8' default is overridden; 'TIMEOUT 60' and 'EXTRA 1' remain.
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['WORKERS'], 'WORKERS 4 TIMEOUT 80')
        self.assertEqual(result_dict['TIMEOUT'], 'TIMEOUT 60')
        self.assertEqual(result_dict['EXTRA'], 'EXTRA 1')

    # 5b. Semicolon-separated string overrides matching defaults
    def test_semicolon_separated_overrides_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60', 'EXTRA 1']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4; TIMEOUT 80', defaults)
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['WORKERS'], 'WORKERS 4')
        self.assertEqual(result_dict['TIMEOUT'], 'TIMEOUT 80')
        self.assertEqual(result_dict['EXTRA'], 'EXTRA 1')

    # 5c. Space-separated explicit kept as single arg, non-overlapping defaults are merged
    def test_space_separated_partial_override_with_defaults(self):
        defaults = [['_FREE_RESOURCE_ON_THREAD TRUE', 'TIMEOUT 100', 'WORKERS 8']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4 TIMEOUT 80', defaults)
        # Single arg 'WORKERS 4 TIMEOUT 80' overrides 'WORKERS 8' default only
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['WORKERS'], 'WORKERS 4 TIMEOUT 80')
        self.assertEqual(result_dict['TIMEOUT'], 'TIMEOUT 100')
        self.assertEqual(result_dict['_FREE_RESOURCE_ON_THREAD'], '_FREE_RESOURCE_ON_THREAD TRUE')

    # 6. None input with defaults - deep copy of defaults
    def test_none_uses_defaults(self):
        defaults = [['WORKERS 8', 'TIMEOUT 60']]
        result = fix_modulesArgs(['/mod.so'], None, defaults)
        self.assertEqual(result, defaults)
        # Verify it's a deep copy
        result[0][0] = 'MODIFIED'
        self.assertEqual(defaults[0][0], 'WORKERS 8')

    # 7. List of strings with defaults - overlapping and non-overlapping keys
    def test_list_of_strings_with_defaults(self):
        defaults = [['K1 default1', 'K2 default2', 'K4 default4']]
        result = fix_modulesArgs(['/mod.so'], ['K1 override1', 'K2 override2', 'K3 new3'], defaults)
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['K1'], 'K1 override1')
        self.assertEqual(result_dict['K2'], 'K2 override2')
        self.assertEqual(result_dict['K3'], 'K3 new3')
        self.assertEqual(result_dict['K4'], 'K4 default4')

    # 8. List of lists (multi-module) with defaults - overlapping and non-overlapping keys
    def test_multi_module_with_defaults(self):
        modules = ['/mod1.so', '/mod2.so']
        explicit = [['K1 v1', 'K2 v2'], ['K3 v3']]
        defaults = [['K1 d1', 'K5 d5'], ['K3 d3', 'K4 d4']]
        result = fix_modulesArgs(modules, explicit, defaults)
        # Module 1: K1 overridden, K5 added from defaults
        dict1 = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(dict1['K1'], 'K1 v1')
        self.assertEqual(dict1['K2'], 'K2 v2')
        self.assertEqual(dict1['K5'], 'K5 d5')
        # Module 2: K3 overridden, K4 added from defaults
        dict2 = {arg.split(' ')[0]: arg for arg in result[1]}
        self.assertEqual(dict2['K3'], 'K3 v3')
        self.assertEqual(dict2['K4'], 'K4 d4')


    # 9. Case-insensitive matching between explicit args and defaults (semicolons)
    def test_case_insensitive_override(self):
        # Uppercase explicit overrides lowercase defaults (using semicolons for multiple args)
        defaults = [['workers 8', 'timeout 60', 'EXTRA 1', 'MIxEd 7', 'lower true']]
        result = fix_modulesArgs(['/mod.so'], 'WORKERS 4; TIMEOUT 80; miXed 0; LOWER false', defaults)
        result_dict = {arg.split(' ')[0]: arg for arg in result[0]}
        self.assertEqual(result_dict['WORKERS'], 'WORKERS 4')
        self.assertEqual(result_dict['TIMEOUT'], 'TIMEOUT 80')
        self.assertEqual(result_dict['EXTRA'], 'EXTRA 1')
        self.assertEqual(result_dict['miXed'], 'miXed 0')
        self.assertEqual(result_dict['LOWER'], 'LOWER false')
        self.assertNotIn('workers', result_dict)
        self.assertNotIn('timeout', result_dict)
        self.assertNotIn('MIxEd', result_dict)
        self.assertNotIn('lower', result_dict)

    # 10. Regression test: space-separated moduleArgs without semicolons should NOT
    # be split into key-value pairs. They should be kept as a single arg string,
    # matching the pre-v0.7.22 behavior.
    def test_space_separated_args_not_split_into_pairs(self):
        result = fix_modulesArgs(['module.so'], 'DEFAULT_DIALECT 2 WORKERS 4 _FREE_RESOURCE_ON_THREAD FALSE')
        # Should be kept as ONE arg string, not split into pairs
        self.assertEqual(result, [['DEFAULT_DIALECT 2 WORKERS 4 _FREE_RESOURCE_ON_THREAD FALSE']])

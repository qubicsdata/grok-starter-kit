"""Every row of the runner parameterization table (the 19 router paths, then identity, policy and fixture rows)
maps to the tests that cover it. This module checks the map itself: 19 path rows, every row covered, every named
test loadable (from this suite or the runner suite next to it)."""
import unittest
import k5support as K  # noqa: F401  (sandbox + sys.path for the runner suite)

C, G, I, B, S, X = "test_k5_config", "test_k5_gate", "test_k5_identity", "test_k5_backlog", "test_k5_static", \
    "test_k5_script"
N = "test_k5_generic"
EXPAND = C + ".KitHomeFromEnvTests.test_every_kit_home_key_is_expanded"  # one subTest per key

# The 19 hardcoded paths of the source, in table order.
PATH_ROWS = {
    "P01 usage-line doc path (run-claude.sh)": [S + ".DocReferenceTests.test_script_and_cli_doc_references_resolve_in_the_kit",
                                                S + ".NoOwnerStringsTests.test_no_leftovers_from_the_source"],
    "P02 router-docs path (run-claude.sh)": [S + ".DocReferenceTests.test_script_and_cli_doc_references_resolve_in_the_kit"],
    "P03 runner.env_file": [X + ".EnvFileTests.test_empty_env_file_sources_nothing",
                            X + ".EnvFileTests.test_configured_env_file_is_sourced",
                            X + ".EnvFileTests.test_missing_env_file_refuses",
                            C + ".KitHomeFromEnvTests.test_env_file_stays_empty",
                            S + ".NoBuiltInPathsTests.test_script_sources_only_configured_files"],
    "P04 runner.flags_file": [EXPAND, X + ".FlagsAndBashEnvTests.test_flags_come_from_the_configured_file",
                              X + ".FlagsAndBashEnvTests.test_missing_flags_file_refuses",
                              S + ".TemplateTests.test_flags_template_is_valid_bash_with_the_three_lists"],
    "P05 CLAUDE_ROUTER_DIR": [X + ".PromptsAndLogsTests.test_router_dir_defaults_to_the_kit_runner_dir",
                              S + ".NoBuiltInPathsTests.test_no_absolute_path_in_runner_code"],
    "P06 run log dir (paths.logs)": [X + ".PromptsAndLogsTests.test_outputs_go_to_the_configured_logs"],
    "P07 runner.prompts_dir": [EXPAND, X + ".PromptsAndLogsTests.test_prompt_from_prompts_dir"],
    "P08 runner.bash_env_file": [EXPAND, X + ".FlagsAndBashEnvTests.test_claude_env_file_is_the_configured_bash_env_file",
                                 S + ".NoBuiltInPathsTests.test_claude_env_file_comes_from_config",
                                 S + ".TemplateTests.test_bash_env_template_holds_no_secret_values"],
    "P09 config comment path": [C + ".ExampleTemplateTests.test_every_path_key_of_the_example_uses_kit_home",
                                S + ".ExampleConfigTests.test_example_is_valid_json_with_comment_naming_kit_home"],
    "P10 usage.probe_dir": [EXPAND],
    "P11 paths.logs": [EXPAND, C + ".KitHomeFromEnvTests.test_cr_overrides_still_win"],
    "P12 paths.queue": [EXPAND],
    "P13 paths.runner": [EXPAND],
    "P14 backlog.queue": [EXPAND],
    "P15 backlog.state_file": [EXPAND],
    "P16 backlog.prompt_dir": [EXPAND],
    "P17 runner.pidfile": [EXPAND, G + ".EnabledGateTests.test_disabled_refuses_loop_and_tick"],
    "P18 runner.stop_file": [EXPAND, G + ".EnabledGateTests.test_refusal_does_not_touch_an_existing_runner_state"],
    "P19 runner.out": [EXPAND],
}

OTHER_ROWS = {
    "existing CR_* env overrides kept": [C + ".KitHomeFromEnvTests.test_cr_overrides_still_win"],
    "runner.mcp_cleanup_pattern (empty = off)": [X + ".McpCleanupTests.test_empty_pattern_never_calls_pkill",
                                                 X + ".McpCleanupTests.test_pattern_set_calls_pkill_with_it",
                                                 S + ".NoBuiltInPathsTests.test_mcp_cleanup_has_no_built_in_pattern"],
    "backlog.group_limits {}": [B + ".GroupLimitsTests.test_example_has_no_groups",
                                B + ".GroupLimitsTests.test_empty_group_limits_cap_nothing"],
    "runner.commit_identity": [I + ".CommitIdentityTests.test_configured_identity_is_used",
                               I + ".CommitIdentityTests.test_neither_skips_the_commit_and_logs_why",
                               S + ".NoOwnerStringsTests.test_no_built_in_git_identity"],
    "backlog.guard_preamble (<your-name>)": [B + ".GuardPreambleTests.test_example_preamble_is_generic",
                                             B + ".GuardPreambleTests.test_empty_or_missing_preamble_holds_the_backlog"],
    "backlog.quiet_hours.tz (${KIT_TZ}, code default UTC)": [C + ".KitHomeFromEnvTests.test_quiet_hours_run_in_the_expanded_tz",
                                                             B + ".QuietHoursTzTests.test_missing_tz_means_utc",
                                                             S + ".NoOwnerStringsTests.test_no_city_time_zone"],
    "policy values (safe limits)": ["test_operating_limits.SafeLimitsConfigTests.test_caps",
                                    "test_operating_limits.SafeLimitsConfigTests.test_pacing_values"],
    "tmux probe removed": ["test_operating_limits.NoTmuxTests.test_tmux_path_removed_even_if_config_says_tmux"],
    "real captured fixtures left out": ["test_fixture_privacy.RunnerTreePrivacy.test_no_real_capture_names"],
}

# Runner items beyond the table.
SPEC_ITEMS = {
    "runner.enabled gate in cr sched": [G + ".EnabledGateTests.test_disabled_refuses_loop_and_tick",
                                        G + ".EnabledGateTests.test_missing_or_non_boolean_enabled_refuses"],
    "ANTHROPIC_API_KEY refused (kept)": [G + ".ApiKeyRefusalTests.test_api_key_refuses_even_when_enabled",
                                         X + ".ApiKeyTests.test_api_key_in_env_refuses"],
    "${KIT_HOME} / ${KIT_TZ} from env or kit.config": [C + ".KitHomeFromKitConfigTests.test_kit_home_and_tz_from_kit_config"],
    "no built-in paths or owner strings": [S + ".NoBuiltInPathsTests.test_no_absolute_path_in_runner_code",
                                           S + ".NoOwnerStringsTests.test_no_leftovers_from_the_source",
                                           N + ".GenericTextTests.test_no_leftover_names_from_the_source",
                                           N + ".GenericTextTests.test_no_host_specific_env_names"],
    "comments and strings generic": [N + ".GenericTextTests.test_no_setup_notes_in_comments_and_docs",
                                     N + ".GenericTextTests.test_no_dates_in_runner_code_docs_or_config_prose",
                                     N + ".GenericTextTests.test_no_work_package_words_in_code_strings"],
    "routes table (opus / sonnet / haiku opt-in / optional Fable)": [
        N + ".RoutesTableTests.test_opus_for_security_architecture_and_core_work",
        N + ".RoutesTableTests.test_sonnet_for_routine_edits_and_docs",
        N + ".RoutesTableTests.test_haiku_only_when_opted_in",
        N + ".RoutesTableTests.test_fable_routes_are_optional_names",
        N + ".RoutesTableTests.test_reasons_are_generic"],
    "models / task_type_aliases / profiles, experiments {}": [
        N + ".RoutesTableTests.test_models_and_fallbacks", N + ".RoutesTableTests.test_aliases_point_at_routes",
        N + ".RoutesTableTests.test_profiles_turn_off_only_public_plugins",
        N + ".RoutesTableTests.test_experiments_are_empty"],
    "complete example config": [N + ".CompleteExampleTests.test_scheduler_runs_on_the_example_alone",
                                N + ".CompleteExampleTests.test_overlay_adds_only_synthetic_experiments"],
    "/usage probe env (generic + usage.probe_unset_env)": [N + ".ProbeEnvTests.test_probe_unsets_only_generic_names_by_default",
                                                          N + ".ProbeEnvTests.test_probe_unsets_the_configured_names"],
}


class RowMapTests(unittest.TestCase):
    def test_nineteen_path_rows(self):
        self.assertEqual(len(PATH_ROWS), 19)
        self.assertEqual([k[:3] for k in PATH_ROWS], ["P%02d" % i for i in range(1, 20)])

    def test_every_row_has_a_loadable_test(self):
        loader = unittest.TestLoader()
        for row, ids in list(PATH_ROWS.items()) + list(OTHER_ROWS.items()) + list(SPEC_ITEMS.items()):
            with self.subTest(row=row):
                self.assertTrue(ids)
                for tid in ids:
                    suite = loader.loadTestsFromName(tid)
                    self.assertEqual(suite.countTestCases(), 1, tid)
                    self.assertNotEqual(type(next(iter(suite))).__name__, "_FailedTest", tid)

    def test_every_kit_home_key_is_in_a_path_row(self):
        names = " ".join(PATH_ROWS)
        for sect, key in K.KIT_HOME_KEYS:
            if (sect, key) == ("runner", "script"):  # not a section 6 row; expanded and checked all the same
                continue
            with self.subTest(key="%s.%s" % (sect, key)):
                self.assertIn("%s.%s" % (sect, key), names)


if __name__ == "__main__":
    unittest.main()

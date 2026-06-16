import json
import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from unittest import mock

import FreeCAD as App
import Mesh
import Part

from freecad.AutoBodyExport import core as export


@contextmanager
def temporary_directory():
    root = os.environ.get("AUTOBODYEXPORT_TEST_TMP")
    if root:
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, f"t{uuid.uuid4().hex[:8]}")
        os.makedirs(path)
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)
        return
    with tempfile.TemporaryDirectory() as directory:
        yield directory


class AutoBodyExportCoreTests(unittest.TestCase):
    def setUp(self):
        export.clear_document_states()
        export.save_export_options(
            export.ExportOptions(
                export_step=True,
                export_stl=False,
                show_dialog=True,
            )
        )

    def tearDown(self):
        export.clear_document_states()

    def test_inventory_includes_nested_parts_unparented_and_empty_parts(self):
        document = App.newDocument("InventoryTest")
        outer = document.addObject("App::Part", "OuterPart")
        inner = document.addObject("App::Part", "InnerPart")
        document.addObject("App::Part", "EmptyPart")
        outer.addObject(inner)
        nested_body = document.addObject("PartDesign::Body", "NestedBody")
        inner.addObject(nested_body)
        document.addObject("PartDesign::Body", "LooseBody")

        inventory = export.build_inventory(document)

        self.assertEqual(
            {part.object_name for part in inventory.parts},
            {"OuterPart", "InnerPart", "EmptyPart"},
        )
        inner_info = next(part for part in inventory.parts if part.object_name == "InnerPart")
        self.assertEqual(inner_info.parent_part_id, "part:OuterPart")
        nested_info = next(body for body in inventory.bodies if body.object_name == "NestedBody")
        self.assertEqual(nested_info.parent_part_id, "part:InnerPart")
        loose_info = next(body for body in inventory.bodies if body.object_name == "LooseBody")
        self.assertIsNone(loose_info.parent_part_id)
        App.closeDocument(document.Name)

    def test_reconcile_preserves_selection_and_selects_new_body(self):
        first = export.Inventory(
            parts=(export.PartInfo("Part", "Part", None),),
            bodies=(export.BodyInfo("Body", "Body", "part:Part"),),
        )
        state, new_ids = export.reconcile_document_state(r"C:\models\sample.FCStd", first, None)
        self.assertEqual(new_ids, {"part:Part", "body:Body"})
        self.assertEqual(state.selected_target_ids, {"body:Body"})
        self.assertFalse(state.target_groups)

        state.selected_target_ids.clear()
        second = export.Inventory(
            parts=first.parts,
            bodies=first.bodies + (export.BodyInfo("Body001", "Body 2", "part:Part"),),
        )
        next_state, new_ids = export.reconcile_document_state(
            r"C:\models\sample.FCStd", second, state
        )
        self.assertEqual(new_ids, {"body:Body001"})
        self.assertEqual(next_state.selected_target_ids, {"body:Body001"})

    def test_reconcile_prunes_deleted_items(self):
        previous = export.DocumentState(
            path=r"C:\models\sample.FCStd",
            known_item_ids={
                "part:Part",
                "body:Body",
                "body:Deleted",
            },
            selected_target_ids={"body:Body", "body:Deleted"},
            target_groups=[{"body:Body", "body:Deleted"}],
        )
        inventory = export.Inventory(
            parts=(export.PartInfo("Part", "Part", None),),
            bodies=(export.BodyInfo("Body", "Body", "part:Part"),),
        )
        state, new_ids = export.reconcile_document_state(previous.path, inventory, previous)
        self.assertFalse(new_ids)
        self.assertEqual(
            state.known_item_ids,
            {"part:Part", "body:Body"},
        )
        self.assertEqual(state.selected_target_ids, {"body:Body"})
        self.assertFalse(state.target_groups)

    def test_inventory_includes_part_objects_but_excludes_body_members(self):
        document = App.newDocument("ObjectInventoryTest")
        part = document.addObject("App::Part", "Part")
        body = document.addObject("PartDesign::Body", "Body")
        part.addObject(body)
        body_feature = body.newObject("PartDesign::Feature", "BodyFeature")
        body_feature.Shape = Part.makeBox(1, 1, 1)
        standalone = document.addObject("Part::Feature", "Standalone")
        standalone.Shape = Part.makeCylinder(2, 5)
        part.addObject(standalone)
        document.recompute()

        inventory = export.build_inventory(document)

        self.assertEqual(
            {obj.object_name for obj in inventory.objects},
            {"Standalone"},
        )
        self.assertEqual(inventory.object_ids, {"object:Standalone"})
        self.assertEqual(
            export.groupable_target_ids_by_parent(inventory),
            {"part:Part": {"body:Body", "object:Standalone"}},
        )
        App.closeDocument(document.Name)

    def test_grouping_is_hidden_for_parts_with_only_one_target(self):
        inventory = export.Inventory(
            parts=(
                export.PartInfo("SinglePart", "Single", None),
                export.PartInfo("MultiPart", "Multi", None),
            ),
            bodies=(
                export.BodyInfo("SingleBody", "Single Body", "part:SinglePart"),
                export.BodyInfo("BodyA", "Body A", "part:MultiPart"),
                export.BodyInfo("BodyB", "Body B", "part:MultiPart"),
            ),
        )

        self.assertEqual(
            export.groupable_target_ids_by_parent(inventory),
            {"part:MultiPart": {"body:BodyA", "body:BodyB"}},
        )

    def test_groups_merge_transitively_and_stay_inside_their_part(self):
        inventory = export.Inventory(
            parts=(
                export.PartInfo("PartA", "Part A", None),
                export.PartInfo("PartB", "Part B", None),
            ),
            bodies=(
                export.BodyInfo("A", "A", "part:PartA"),
                export.BodyInfo("B", "B", "part:PartA"),
                export.BodyInfo("C", "C", "part:PartA"),
                export.BodyInfo("D", "D", "part:PartB"),
                export.BodyInfo("E", "E", "part:PartB"),
            ),
        )

        groups = export.normalize_target_groups(
            inventory,
            [
                {"body:A", "body:B"},
                {"body:B", "body:C"},
                {"body:C", "body:D", "body:E"},
            ],
        )

        self.assertEqual(
            groups,
            [
                {"body:A", "body:B", "body:C"},
                {"body:D", "body:E"},
            ],
        )
        self.assertEqual(
            export.synchronize_group_selection({"body:A"}, groups),
            {"body:A", "body:B", "body:C"},
        )

    def test_group_visuals_use_matching_labels_and_distinct_colors(self):
        visuals = export.build_group_visuals(
            [
                {"body:A", "body:B", "body:C"},
                {"body:D", "body:E"},
            ]
        )

        self.assertEqual(visuals["body:A"], visuals["body:B"])
        self.assertEqual(visuals["body:B"], visuals["body:C"])
        self.assertEqual(
            visuals["body:A"][0],
            export.tr("Group {number} - {count} items").format(number=1, count=3),
        )
        self.assertEqual(
            visuals["body:D"][0],
            export.tr("Group {number} - {count} items").format(number=2, count=2),
        )
        self.assertNotEqual(visuals["body:A"][1], visuals["body:D"][1])

    def test_legacy_part_group_is_migrated_to_target_group(self):
        inventory = export.Inventory(
            parts=(export.PartInfo("Part", "Part", None),),
            bodies=(
                export.BodyInfo("BodyA", "Body A", "part:Part"),
                export.BodyInfo("BodyB", "Body B", "part:Part"),
            ),
        )
        previous = export.DocumentState(
            path=r"C:\models\sample.FCStd",
            known_item_ids={"part:Part", "body:BodyA", "body:BodyB", "group:Part"},
            selected_target_ids={"group:Part"},
        )

        state, new_ids = export.reconcile_document_state(previous.path, inventory, previous)

        self.assertFalse(new_ids)
        self.assertEqual(state.selected_target_ids, {"body:BodyA", "body:BodyB"})
        self.assertEqual(state.target_groups, [{"body:BodyA", "body:BodyB"}])

    def test_filename_sanitization_and_part_omission(self):
        self.assertEqual(
            export.compose_export_stem(
                "model",
                'Part: "A"',
                "Body/One",
                "Body",
                "Part",
            ),
            "model_Part_ _A_Body_One",
        )
        self.assertEqual(
            export.compose_export_stem("model", None, "Body", "Body"),
            "model_Body",
        )

    def test_group_filename_uses_only_body_names(self):
        body_a = export.BodyInfo("BodyA", "Body 1", "part:Part")
        body_b = export.BodyInfo("BodyB", "Body 2", "part:Part")
        standalone = export.ObjectInfo("Standalone", "Pin", "Part::Feature", "part:Part")

        self.assertEqual(
            export.group_filename_component([body_a, standalone]),
            ("Body 1", "BodyA"),
        )
        self.assertEqual(
            export.group_filename_component([body_a, body_b, standalone]),
            ("Body 1_Body 2", "BodyA_BodyB"),
        )
        self.assertEqual(
            export.group_filename_component([standalone]),
            ("Group", "Group"),
        )

    def test_existing_latest_is_archived_with_matching_version_name(self):
        with temporary_directory() as directory:
            output_path = export.latest_export_path(directory, "model", "step")
            with open(output_path, "w") as output_file:
                output_file.write("latest 0")

            for version in range(2):
                temporary_path = os.path.join(directory, f"temporary{version}.step")
                with open(temporary_path, "w") as temporary_file:
                    temporary_file.write(f"latest {version + 1}")
                archive_path = export.replace_latest_export(
                    temporary_path,
                    output_path,
                    export.next_old_version_number(directory),
                )
                expected_archive_path = os.path.join(
                    directory,
                    "old_versions",
                    f"v{version}",
                    f"model_v{version}.step",
                )
                self.assertEqual(archive_path, expected_archive_path)
                self.assertTrue(os.path.isfile(expected_archive_path))
                with open(expected_archive_path) as archive_file:
                    self.assertEqual(archive_file.read(), f"latest {version}")

            with open(output_path) as output_file:
                self.assertEqual(output_file.read(), "latest 2")

    def test_failed_latest_replacement_restores_previous_file(self):
        with temporary_directory() as directory:
            output_path = export.latest_export_path(directory, "model", "step")
            temporary_path = os.path.join(directory, "temporary.step")
            with open(output_path, "w") as output_file:
                output_file.write("previous")
            with open(temporary_path, "w") as temporary_file:
                temporary_file.write("new")

            real_replace = export.os.replace
            replacement_attempted = False

            def fail_new_latest(source, destination):
                nonlocal replacement_attempted
                if source == temporary_path and destination == output_path:
                    replacement_attempted = True
                    raise OSError("simulated replacement failure")
                return real_replace(source, destination)

            with mock.patch.object(export.os, "replace", side_effect=fail_new_latest):
                with self.assertRaises(OSError):
                    export.replace_latest_export(temporary_path, output_path, 0)

            self.assertTrue(replacement_attempted)
            with open(output_path) as output_file:
                self.assertEqual(output_file.read(), "previous")
            self.assertFalse(
                os.path.exists(
                    os.path.join(
                        directory,
                        "old_versions",
                        "v0",
                        "model_v0.step",
                    )
                )
            )

    def test_exports_archive_old_versions_and_reload_latest(self):
        document = App.newDocument("ExportTest")
        part = document.addObject("App::Part", "ExportPart")
        part.Label = "Part/A"
        body = document.addObject("PartDesign::Body", "ExportBody")
        body.Label = "Body:Main"
        part.addObject(body)
        feature = body.newObject("PartDesign::Feature", "Solid")
        feature.Shape = Part.makeBox(10, 20, 30)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "sample.FCStd")
            for _ in range(3):
                failures = export._export_selected_bodies(
                    document=document,
                    filepath=filepath,
                    inventory=inventory,
                    selected_body_ids={"body:ExportBody"},
                    export_step=True,
                    export_stl=True,
                )
                self.assertFalse(failures)

            expected_paths = [
                os.path.join(directory, "step", "sample_Part_A_Body_Main.step"),
                os.path.join(directory, "stl", "sample_Part_A_Body_Main.stl"),
            ]
            for expected_path in expected_paths:
                self.assertTrue(os.path.isfile(expected_path), expected_path)
                self.assertGreater(os.path.getsize(expected_path), 0)

            for extension in ("step", "stl"):
                for version in range(2):
                    archived_path = os.path.join(
                        directory,
                        extension,
                        "old_versions",
                        f"v{version}",
                        f"sample_Part_A_Body_Main_v{version}.{extension}",
                    )
                    self.assertTrue(os.path.isfile(archived_path), archived_path)
                    self.assertGreater(os.path.getsize(archived_path), 0)

            imported_shape = Part.Shape()
            imported_shape.read(expected_paths[0])
            self.assertFalse(imported_shape.isNull())

            imported_mesh = Mesh.Mesh(expected_paths[1])
            self.assertGreater(imported_mesh.CountFacets, 0)

        App.closeDocument(document.Name)

    def test_multiple_outputs_share_one_archive_version_per_format(self):
        document = App.newDocument("SharedArchiveVersionTest")
        part = document.addObject("App::Part", "ExportPart")
        for name in ("BodyA", "BodyB"):
            body = document.addObject("PartDesign::Body", name)
            part.addObject(body)
            feature = body.newObject("PartDesign::Feature", f"{name}Solid")
            feature.Shape = Part.makeBox(5, 5, 5)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "sample.FCStd")
            for _ in range(2):
                failures = export._export_selected_targets(
                    document=document,
                    filepath=filepath,
                    inventory=inventory,
                    selected_target_ids={"body:BodyA", "body:BodyB"},
                    export_step=True,
                    export_stl=False,
                )
                self.assertFalse(failures)

            archive_directory = os.path.join(directory, "step", "old_versions", "v0")
            self.assertEqual(
                sorted(os.listdir(archive_directory)),
                [
                    "sample_ExportPart_BodyA_v0.step",
                    "sample_ExportPart_BodyB_v0.step",
                ],
            )

        App.closeDocument(document.Name)

    def test_exports_part_targets_as_selected_group(self):
        document = App.newDocument("GroupedExportTest")
        part = document.addObject("App::Part", "ExportPart")
        part.Label = "Assembly"
        body = document.addObject("PartDesign::Body", "ExportBody")
        body.Label = "Main Body"
        part.addObject(body)
        body_feature = body.newObject("PartDesign::Feature", "BodySolid")
        body_feature.Shape = Part.makeBox(10, 10, 10)
        second_body = document.addObject("PartDesign::Body", "SecondBody")
        second_body.Label = "Second Body"
        part.addObject(second_body)
        second_feature = second_body.newObject("PartDesign::Feature", "SecondBodySolid")
        second_feature.Shape = Part.makeBox(5, 5, 5)
        standalone = document.addObject("Part::Feature", "Standalone")
        standalone.Label = "Pin"
        standalone.Shape = Part.makeCylinder(2, 10)
        part.addObject(standalone)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "sample.FCStd")
            failures = export._export_selected_targets(
                document=document,
                filepath=filepath,
                inventory=inventory,
                selected_target_ids={"object:Standalone"},
                export_step=True,
                export_stl=False,
                target_groups=[
                    {
                        "body:ExportBody",
                        "body:SecondBody",
                        "object:Standalone",
                    },
                ],
            )
            self.assertFalse(failures)
            grouped_path = os.path.join(
                directory,
                "step",
                "sample_Assembly_Main Body_Second Body.step",
            )
            self.assertTrue(os.path.isfile(grouped_path))
            self.assertFalse(
                os.path.isfile(
                    os.path.join(
                        directory,
                        "step",
                        "sample_Assembly_Main Body_Second Body_Pin.step",
                    )
                )
            )

            grouped_shape = Part.Shape()
            grouped_shape.read(grouped_path)
            self.assertFalse(grouped_shape.isNull())
            self.assertGreaterEqual(len(grouped_shape.Solids), 3)

        App.closeDocument(document.Name)

    def test_duplicate_labels_produce_distinct_first_run_outputs(self):
        document = App.newDocument("DuplicateLabelTest")
        part = document.addObject("App::Part", "Assembly")
        for name, size in (("BodyA", 2), ("BodyB", 3)):
            body = document.addObject("PartDesign::Body", name)
            body.Label = "Same Label"
            part.addObject(body)
            feature = body.newObject("PartDesign::Feature", name + "Feature")
            feature.Shape = Part.makeBox(size, size, size)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            result = export._run_export_selected_targets(
                document=document,
                filepath=os.path.join(directory, "model.FCStd"),
                inventory=inventory,
                selected_target_ids=inventory.body_ids,
                target_groups=(),
                options=export.ExportOptions(True, False, False, enabled=True),
            )
            self.assertFalse(result.failures)
            self.assertEqual(len(result.generated_files), 2)
            self.assertEqual(
                len({os.path.basename(path) for path in result.generated_files}),
                2,
            )
            self.assertFalse(os.path.isdir(os.path.join(directory, "step", "old_versions")))

        App.closeDocument(document.Name)

    def test_object_only_groups_do_not_collide(self):
        document = App.newDocument("ObjectGroupCollisionTest")
        part = document.addObject("App::Part", "Assembly")
        for index, name in enumerate(("A", "B", "C", "D"), start=1):
            obj = document.addObject("Part::Feature", name)
            obj.Shape = Part.makeBox(index, index, index)
            part.addObject(obj)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            result = export._run_export_selected_targets(
                document=document,
                filepath=os.path.join(directory, "model.FCStd"),
                inventory=inventory,
                selected_target_ids=inventory.object_ids,
                target_groups=[
                    {"object:A", "object:B"},
                    {"object:C", "object:D"},
                ],
                options=export.ExportOptions(True, False, False, enabled=True),
            )
            self.assertFalse(result.failures)
            self.assertEqual(len(result.generated_files), 2)
            self.assertFalse(os.path.isdir(os.path.join(directory, "step", "old_versions")))

        App.closeDocument(document.Name)

    def test_invalid_group_is_all_or_nothing(self):
        document = App.newDocument("InvalidGroupTest")
        part = document.addObject("App::Part", "Assembly")
        valid = document.addObject("PartDesign::Body", "ValidBody")
        part.addObject(valid)
        valid_feature = valid.newObject("PartDesign::Feature", "ValidFeature")
        valid_feature.Shape = Part.makeBox(2, 2, 2)
        empty = document.addObject("PartDesign::Body", "EmptyBody")
        part.addObject(empty)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            result = export._run_export_selected_targets(
                document=document,
                filepath=os.path.join(directory, "model.FCStd"),
                inventory=inventory,
                selected_target_ids=inventory.body_ids,
                target_groups=[{"body:ValidBody", "body:EmptyBody"}],
                options=export.ExportOptions(True, False, False, enabled=True),
            )
            self.assertTrue(result.failures)
            self.assertFalse(result.generated_files)
            step_directory = os.path.join(directory, "step")
            self.assertFalse(os.path.isdir(step_directory))

        App.closeDocument(document.Name)

    def test_renamed_and_deselected_outputs_are_retired(self):
        document = App.newDocument("StaleOutputTest")
        part = document.addObject("App::Part", "Assembly")
        body = document.addObject("PartDesign::Body", "Body")
        body.Label = "Old Label"
        part.addObject(body)
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        options = export.ExportOptions(True, False, False, enabled=True, history_limit=3)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "model.FCStd")
            inventory = export.build_inventory(document)
            first = export._run_export_selected_targets(
                document,
                filepath,
                inventory,
                inventory.body_ids,
                (),
                options,
            )
            self.assertFalse(first.failures)
            old_path = next(iter(first.generated_files))

            body.Label = "New Label"
            inventory = export.build_inventory(document)
            second = export._run_export_selected_targets(
                document,
                filepath,
                inventory,
                inventory.body_ids,
                (),
                options,
                first.generated_files,
                first.export_signatures,
            )
            self.assertFalse(second.failures)
            self.assertFalse(os.path.exists(old_path))
            self.assertTrue(
                any(
                    "Old Label" in name
                    for _, _, names in os.walk(os.path.join(directory, "step", "old_versions"))
                    for name in names
                )
            )

            third = export._run_export_selected_targets(
                document,
                filepath,
                inventory,
                set(),
                (),
                options,
                second.generated_files,
                second.export_signatures,
            )
            self.assertFalse(third.failures)
            self.assertFalse(third.generated_files)
            self.assertFalse(any(os.path.exists(path) for path in second.generated_files))

        App.closeDocument(document.Name)

    def test_unchanged_export_is_skipped_and_history_is_bounded(self):
        document = App.newDocument("HistoryLimitTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            history_limit=2,
            skip_unchanged=True,
        )

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "model.FCStd")
            result = export._run_export_selected_targets(
                document,
                filepath,
                inventory,
                inventory.body_ids,
                (),
                options,
            )
            unchanged = export._run_export_selected_targets(
                document,
                filepath,
                inventory,
                inventory.body_ids,
                (),
                options,
                result.generated_files,
                result.export_signatures,
            )
            self.assertFalse(unchanged.failures)
            self.assertFalse(os.path.isdir(os.path.join(directory, "step", "old_versions")))

            previous = unchanged
            for size in (3, 4, 5):
                feature.Shape = Part.makeBox(size, size, size)
                document.recompute()
                inventory = export.build_inventory(document)
                previous = export._run_export_selected_targets(
                    document,
                    filepath,
                    inventory,
                    inventory.body_ids,
                    (),
                    options,
                    previous.generated_files,
                    previous.export_signatures,
                )
                self.assertFalse(previous.failures)
            versions = [
                name
                for name in os.listdir(os.path.join(directory, "step", "old_versions"))
                if name.startswith("v")
            ]
            self.assertEqual(len(versions), 2)

        App.closeDocument(document.Name)

    def test_long_labels_are_truncated_and_existing_files_are_protected(self):
        document = App.newDocument("FilenameSafetyTest")
        part = document.addObject("App::Part", "Assembly")
        body = document.addObject("PartDesign::Body", "Body")
        body.Label = "X" * 300
        part.addObject(body)
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            step_directory = os.path.join(directory, "step")
            os.makedirs(step_directory)
            unmanaged_path = os.path.join(
                step_directory,
                export.render_export_stem(
                    export.DEFAULT_FILENAME_TEMPLATE,
                    "model",
                    "Assembly",
                    body.Label,
                    body.Name,
                    "body:Body",
                )
                + ".step",
            )
            with open(unmanaged_path, "w") as unmanaged:
                unmanaged.write("do not replace")

            result = export._run_export_selected_targets(
                document,
                os.path.join(directory, "model.FCStd"),
                inventory,
                inventory.body_ids,
                (),
                export.ExportOptions(True, False, False, enabled=True),
            )
            self.assertFalse(result.failures)
            self.assertEqual(len(result.generated_files), 1)
            with open(unmanaged_path) as unmanaged:
                self.assertEqual(unmanaged.read(), "do not replace")
            generated_path = next(iter(result.generated_files))
            self.assertNotEqual(generated_path, export.normalize_document_path(unmanaged_path))
            self.assertLessEqual(
                len(os.path.splitext(os.path.basename(generated_path))[0]),
                export.MAX_FILENAME_STEM_LENGTH,
            )

        App.closeDocument(document.Name)

    def test_custom_output_directory_uses_document_subdirectory(self):
        document = App.newDocument("CustomOutputTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as document_directory:
            with temporary_directory() as custom_directory:
                options = export.ExportOptions(
                    True,
                    False,
                    False,
                    enabled=True,
                    output_mode=export.OUTPUT_MODE_CUSTOM,
                    custom_output_directory=custom_directory,
                )
                result = export._run_export_selected_targets(
                    document,
                    os.path.join(document_directory, "sample.FCStd"),
                    inventory,
                    inventory.body_ids,
                    (),
                    options,
                )
                self.assertFalse(result.failures)
                generated_path = next(iter(result.generated_files))
                expected_subdirectory = "sample_" + export._short_hash(
                    export.path_comparison_key(document_directory)
                )
                self.assertTrue(
                    generated_path.startswith(
                        export.normalize_document_path(
                            os.path.join(custom_directory, expected_subdirectory)
                        )
                    )
                )

        App.closeDocument(document.Name)

    def test_custom_output_separates_same_named_documents(self):
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=r"C:\exports",
        )

        first = export.resolve_output_root(r"C:\projects\one\sample.FCStd", options)
        second = export.resolve_output_root(r"C:\projects\two\sample.FCStd", options)

        self.assertNotEqual(first, second)
        self.assertTrue(os.path.basename(first).startswith("sample_"))
        self.assertTrue(os.path.basename(second).startswith("sample_"))

    def test_document_dir_token_uses_document_directory_without_hash_subdirectory(self):
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=export.DOCUMENT_DIRECTORY_TOKEN + "/export",
        )

        root = export.resolve_output_root(r"C:\projects\one\sample.FCStd", options)

        self.assertEqual(
            export.normalize_document_path(root),
            export.normalize_document_path(r"C:\projects\one\export"),
        )

    def test_output_directory_template_allows_document_parent_token(self):
        self.assertTrue(
            export.validate_output_directory_template(
                export.DOCUMENT_PARENT_DIRECTORY_TOKEN + "/export"
            )
        )
        self.assertTrue(
            export.validate_output_directory_template(
                export.DOCUMENT_DIRECTORY_TOKEN + "/../export"
            )
        )
        self.assertFalse(export.validate_output_directory_template("{unknown}/export"))

    def test_document_dir_token_allows_parent_segments(self):
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=export.DOCUMENT_DIRECTORY_TOKEN + "/../export",
        )

        root = export.resolve_output_root(r"C:\projects\one\sample.FCStd", options)

        self.assertEqual(
            export.normalize_document_path(root),
            export.normalize_document_path(r"C:\projects\export"),
        )

    def test_document_parent_dir_token_uses_parent_directory(self):
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=export.DOCUMENT_PARENT_DIRECTORY_TOKEN + "/export",
        )

        root = export.resolve_output_root(r"C:\projects\one\sample.FCStd", options)

        self.assertEqual(
            export.normalize_document_path(root),
            export.normalize_document_path(r"C:\projects\export"),
        )

    def test_document_state_custom_output_overrides_global_output(self):
        options = export.ExportOptions(
            True,
            False,
            False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=r"C:\global",
        )
        state = export.DocumentState(
            path=r"C:\projects\one\sample.FCStd",
            known_item_ids=set(),
            selected_target_ids=set(),
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=export.DOCUMENT_DIRECTORY_TOKEN + "/project_export",
        )

        root = export.resolve_output_root(state.path, options, state)

        self.assertEqual(
            export.normalize_document_path(root),
            export.normalize_document_path(r"C:\projects\one\project_export"),
        )

    def test_changing_output_root_retires_previous_managed_files(self):
        document = App.newDocument("OutputRootChangeTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as document_directory:
            with temporary_directory() as custom_directory:
                filepath = os.path.join(document_directory, "model.FCStd")
                first = export._run_export_selected_targets(
                    document,
                    filepath,
                    inventory,
                    inventory.body_ids,
                    (),
                    export.ExportOptions(True, False, False, enabled=True),
                )
                old_path = next(iter(first.generated_files))

                second = export._run_export_selected_targets(
                    document,
                    filepath,
                    inventory,
                    inventory.body_ids,
                    (),
                    export.ExportOptions(
                        True,
                        False,
                        False,
                        enabled=True,
                        output_mode=export.OUTPUT_MODE_CUSTOM,
                        custom_output_directory=custom_directory,
                    ),
                    previous_managed_files=first.generated_files,
                    previous_signatures=first.export_signatures,
                    previous_output_roots=first.managed_output_roots,
                )

                self.assertFalse(second.failures)
                self.assertFalse(os.path.exists(old_path))
                self.assertTrue(
                    os.path.isdir(os.path.join(document_directory, "step", "old_versions"))
                )
                new_path = next(iter(second.generated_files))
                expected_root = export.resolve_output_root(
                    filepath,
                    export.ExportOptions(
                        True,
                        False,
                        False,
                        enabled=True,
                        output_mode=export.OUTPUT_MODE_CUSTOM,
                        custom_output_directory=custom_directory,
                    ),
                )
                self.assertTrue(new_path.startswith(expected_root))
                self.assertEqual(
                    second.managed_output_roots,
                    {export.normalize_document_path(expected_root)},
                )

        App.closeDocument(document.Name)

    def test_nested_part_placements_are_applied_to_step_and_stl(self):
        document = App.newDocument("NestedPlacementTest")
        outer = document.addObject("App::Part", "Outer")
        outer.Placement.Base.x = 10
        inner = document.addObject("App::Part", "Inner")
        inner.Placement.Base.x = 5
        outer.addObject(inner)
        obj = document.addObject("Part::Feature", "PlacedObject")
        obj.Shape = Part.makeBox(2, 2, 2)
        obj.Placement.Base.x = 2
        inner.addObject(obj)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            result = export._run_export_selected_targets(
                document,
                os.path.join(directory, "model.FCStd"),
                inventory,
                {"object:PlacedObject"},
                (),
                export.ExportOptions(True, True, False, enabled=True),
            )

            self.assertFalse(result.failures)
            step_path = next(path for path in result.generated_files if path.endswith(".step"))
            stl_path = next(path for path in result.generated_files if path.endswith(".stl"))
            imported_shape = Part.Shape()
            imported_shape.read(step_path)
            imported_mesh = Mesh.Mesh(stl_path)
            self.assertAlmostEqual(imported_shape.BoundBox.XMin, 17.0, places=5)
            self.assertAlmostEqual(imported_mesh.BoundBox.XMin, 17.0, places=5)

        App.closeDocument(document.Name)

    def test_untrusted_managed_path_is_not_retired(self):
        document = App.newDocument("ManagedPathSafetyTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            unrelated_directory = os.path.join(directory, "unrelated")
            os.makedirs(unrelated_directory)
            unrelated_path = os.path.join(unrelated_directory, "keep.step")
            with open(unrelated_path, "w") as unrelated_file:
                unrelated_file.write("keep")

            result = export._run_export_selected_targets(
                document,
                os.path.join(directory, "model.FCStd"),
                inventory,
                set(),
                (),
                export.ExportOptions(True, False, False, enabled=True, history_limit=0),
                previous_managed_files={unrelated_path},
            )

            self.assertFalse(result.failures)
            self.assertTrue(os.path.isfile(unrelated_path))
            self.assertFalse(result.generated_files)

        App.closeDocument(document.Name)

    def test_options_and_document_state_round_trip(self):
        options = export.ExportOptions(
            export_step=False,
            export_stl=True,
            show_dialog=False,
            enabled=True,
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=r"C:\exports",
            filename_template="{document}_{name}",
            history_limit=7,
            stl_linear_deflection=0.25,
            stl_angular_deflection=0.75,
            show_progress=False,
            skip_unchanged=False,
            stl_use_freecad_settings=False,
        )
        export.save_export_options(options)
        self.assertEqual(export.load_export_options(), options)

        state = export.DocumentState(
            path=r"C:\models\sample.FCStd",
            known_item_ids={"part:Part", "body:Body"},
            selected_target_ids={"body:Body"},
            target_groups=[],
            enabled=False,
            generated_files={r"C:\models\step\sample_Body.step"},
            export_signatures={r"C:\models\step\sample_Body.step": "step:signature"},
            managed_output_roots={r"C:\models"},
            output_mode=export.OUTPUT_MODE_CUSTOM,
            custom_output_directory=export.DOCUMENT_DIRECTORY_TOKEN + "/export",
        )
        export.save_document_state(state)
        loaded = export.load_document_state(state.path)

        self.assertIsNotNone(loaded)
        self.assertFalse(loaded.enabled)
        self.assertEqual(
            loaded.managed_output_roots,
            {export.normalize_document_path(r"C:\models")},
        )
        self.assertEqual(
            loaded.generated_files,
            {export.normalize_document_path(r"C:\models\step\sample_Body.step")},
        )
        self.assertEqual(loaded.output_mode, export.OUTPUT_MODE_CUSTOM)
        self.assertEqual(
            loaded.custom_output_directory,
            export.DOCUMENT_DIRECTORY_TOKEN + "/export",
        )

    def test_stl_mesh_settings_default_to_freecad_export_deviation(self):
        class FakeParameterGroup:
            def GetFloat(self, key, default):
                self.request = (key, default)
                return 0.42

        parameter_group = FakeParameterGroup()
        with mock.patch.object(export.App, "ParamGet", return_value=parameter_group) as param_get:
            settings = export.resolve_stl_mesh_settings(export.ExportOptions(False, True, False))

        param_get.assert_called_once_with(export.FREECAD_MESH_PARAMETER_PATH)
        self.assertEqual(
            parameter_group.request,
            (
                export.FREECAD_MESH_MAX_DEVIATION_EXPORT_KEY,
                export.DEFAULT_STL_LINEAR_DEFLECTION,
            ),
        )
        self.assertEqual(settings.source, "freecad")
        self.assertEqual(settings.linear_deflection, 0.42)
        self.assertEqual(settings.angular_deflection, export.DEFAULT_STL_ANGULAR_DEFLECTION)

    def test_manual_stl_mesh_settings_do_not_read_freecad_preferences(self):
        options = export.ExportOptions(
            False,
            True,
            False,
            stl_linear_deflection=0.25,
            stl_angular_deflection=0.75,
            stl_use_freecad_settings=False,
        )
        with mock.patch.object(export.App, "ParamGet") as param_get:
            settings = export.resolve_stl_mesh_settings(options)

        param_get.assert_not_called()
        self.assertEqual(settings.source, "manual")
        self.assertEqual(settings.linear_deflection, 0.25)
        self.assertEqual(settings.angular_deflection, 0.75)

    def test_document_state_uses_embedded_path_when_map_key_is_corrupted(self):
        with temporary_directory() as directory:
            expected_path = os.path.join(directory, "expected.FCStd")
            corrupted_key_path = os.path.join(directory, "wrong.FCStd")
            state = export.DocumentState(
                path=expected_path,
                known_item_ids={"body:Body"},
                selected_target_ids={"body:Body"},
            )
            export.preferences().SetString(
                export.DOCUMENT_STATES_KEY,
                json.dumps(
                    {
                        export.path_comparison_key(corrupted_key_path): state.to_json_value(),
                    }
                ),
            )

            self.assertIsNone(export.load_document_state(corrupted_key_path))
            loaded = export.load_document_state(expected_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.path, export.normalize_document_path(expected_path))

    def test_process_saved_document_exports_opted_in_state_headless(self):
        document = App.newDocument("ProcessSavedDocumentTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "model.FCStd")
            export.save_export_options(
                export.ExportOptions(
                    export_step=True,
                    export_stl=False,
                    show_dialog=False,
                    enabled=True,
                    show_progress=False,
                )
            )
            export.save_document_state(
                export.DocumentState(
                    path=filepath,
                    known_item_ids=inventory.item_ids,
                    selected_target_ids=inventory.body_ids,
                    enabled=True,
                )
            )

            export.process_saved_document(document, filepath)

            output_path = os.path.join(directory, "step", "model_Body.step")
            self.assertTrue(os.path.isfile(output_path))
            saved_state = export.load_document_state(filepath)
            self.assertEqual(
                saved_state.generated_files,
                {export.normalize_document_path(output_path)},
            )
            self.assertEqual(
                saved_state.managed_output_roots,
                {export.normalize_document_path(directory)},
            )

        App.closeDocument(document.Name)

    def test_process_saved_document_uses_document_state_output_directory(self):
        document = App.newDocument("ProcessSavedDocumentCustomOutputTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "model.FCStd")
            export.save_export_options(
                export.ExportOptions(
                    export_step=True,
                    export_stl=False,
                    show_dialog=False,
                    enabled=True,
                    show_progress=False,
                )
            )
            export.save_document_state(
                export.DocumentState(
                    path=filepath,
                    known_item_ids=inventory.item_ids,
                    selected_target_ids=inventory.body_ids,
                    enabled=True,
                    output_mode=export.OUTPUT_MODE_CUSTOM,
                    custom_output_directory=export.DOCUMENT_DIRECTORY_TOKEN + "/export",
                )
            )

            export.process_saved_document(document, filepath)

            output_root = os.path.join(directory, "export")
            output_path = os.path.join(output_root, "step", "model_Body.step")
            self.assertTrue(os.path.isfile(output_path))
            saved_state = export.load_document_state(filepath)
            self.assertEqual(
                saved_state.managed_output_roots,
                {export.normalize_document_path(output_root)},
            )

        App.closeDocument(document.Name)

    def test_process_saved_document_does_nothing_when_globally_disabled(self):
        document = App.newDocument("DisabledProcessTest")
        body = document.addObject("PartDesign::Body", "Body")
        feature = body.newObject("PartDesign::Feature", "Feature")
        feature.Shape = Part.makeBox(2, 2, 2)
        document.recompute()
        inventory = export.build_inventory(document)

        with temporary_directory() as directory:
            filepath = os.path.join(directory, "model.FCStd")
            export.save_document_state(
                export.DocumentState(
                    path=filepath,
                    known_item_ids=inventory.item_ids,
                    selected_target_ids=inventory.body_ids,
                    enabled=True,
                )
            )

            export.process_saved_document(document, filepath)

            self.assertFalse(os.path.exists(os.path.join(directory, "step")))

        App.closeDocument(document.Name)

    def test_document_observer_receives_save_completion(self):
        calls = []
        original_process_saved_document = export.process_saved_document
        observer = export.DocumentObserver()
        document = App.newDocument("ObserverTest")
        try:
            export.process_saved_document = lambda saved_document, filepath: calls.append(
                (saved_document.Name, filepath)
            )
            with temporary_directory() as directory:
                filepath = os.path.join(directory, "observer.FCStd")
                document.saveAs(filepath)
                self.assertEqual(calls, [(document.Name, filepath)])
        finally:
            observer.stop()
            export.process_saved_document = original_process_saved_document
            App.closeDocument(document.Name)

    def test_gui_document_observer_defers_processing_until_save_returns(self):
        calls = []
        scheduled = []
        original_gui_is_available = export.gui_is_available
        original_schedule_gui_task = export.schedule_gui_task
        original_process_saved_document = export.process_saved_document
        observer = export.DocumentObserver()
        document = App.newDocument("DeferredObserverTest")
        try:
            export.gui_is_available = lambda: True
            export.schedule_gui_task = scheduled.append
            export.process_saved_document = lambda saved_document, filepath: calls.append(
                (saved_document.Name, filepath)
            )

            observer.slotFinishSaveDocument(document, r"C:\models\first.FCStd")
            observer.slotFinishSaveDocument(document, r"C:\models\deferred.FCStd")

            self.assertFalse(calls)
            self.assertEqual(len(scheduled), 1)
            scheduled[0]()
            self.assertEqual(
                calls,
                [(document.Name, r"C:\models\deferred.FCStd")],
            )
        finally:
            observer.stop()
            export.gui_is_available = original_gui_is_available
            export.schedule_gui_task = original_schedule_gui_task
            export.process_saved_document = original_process_saved_document
            App.closeDocument(document.Name)


if __name__ == "__main__":
    unittest.main()

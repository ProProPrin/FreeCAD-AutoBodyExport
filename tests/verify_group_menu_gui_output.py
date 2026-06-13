import os

import Mesh
import Part

fixture_directory = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "gui_fixture")
)
group_step_path = os.path.join(
    fixture_directory,
    "step",
    "AutoBodyExportGroupMenuFixture_Multi-target Part_Main Body.step",
)
group_stl_path = os.path.join(
    fixture_directory,
    "stl",
    "AutoBodyExportGroupMenuFixture_Multi-target Part_Main Body.stl",
)

group_shape = Part.Shape()
group_shape.read(group_step_path)
group_mesh = Mesh.Mesh(group_stl_path)

assert len(group_shape.Solids) >= 3, group_step_path
assert group_mesh.CountFacets > 0, group_stl_path

print(f"GROUP_STEP={group_step_path}")
print(f"GROUP_SOLIDS={len(group_shape.Solids)}")
print(f"GROUP_STL={group_stl_path}")
print(f"GROUP_FACETS={group_mesh.CountFacets}")

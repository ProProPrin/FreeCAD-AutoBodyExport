import os

import FreeCAD as App
import Part

output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "gui_fixture",
        "AutoBodyExportGuiFixture.FCStd",
    )
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
document = App.newDocument("AutoBodyExportGuiFixture")

part = document.addObject("App::Part", "FixturePart")
part.Label = "Fixture Part"

body = document.addObject("PartDesign::Body", "FixtureBody")
body.Label = "Fixture Body"
part.addObject(body)

feature = body.newObject("PartDesign::Feature", "FixtureSolid")
feature.Shape = Part.makeBox(12, 18, 24)

loose_body = document.addObject("PartDesign::Body", "LooseBody")
loose_body.Label = "Loose Body"
loose_feature = loose_body.newObject("PartDesign::Feature", "LooseSolid")
loose_feature.Shape = Part.makeCylinder(5, 15)

document.recompute()
document.saveAs(output_path)
App.closeDocument(document.Name)

print(output_path)

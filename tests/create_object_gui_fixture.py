import os

import Part

import FreeCAD as App

document = App.newDocument("AutoBodyExportObjectFixture")
part = document.addObject("App::Part", "FixturePart")
part.Label = "Fixture Part"

body = document.addObject("PartDesign::Body", "FixtureBody")
body.Label = "Fixture Body"
part.addObject(body)
body_feature = body.newObject("PartDesign::Feature", "BodySolid")
body_feature.Shape = Part.makeBox(10, 12, 14)

standalone = document.addObject("Part::Feature", "StandalonePin")
standalone.Label = "Standalone Pin"
standalone.Shape = Part.makeCylinder(2, 14)
part.addObject(standalone)

document.recompute()
output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "gui_fixture",
        "AutoBodyExportObjectFixture.FCStd",
    )
)
document.saveAs(output_path)
print(output_path)

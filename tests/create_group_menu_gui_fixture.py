import os

import Part

import FreeCAD as App

output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "gui_fixture",
        "AutoBodyExportGroupMenuFixture.FCStd",
    )
)

document = App.newDocument("AutoBodyExportGroupMenuFixture")

multi_part = document.addObject("App::Part", "MultiPart")
multi_part.Label = "Multi-target Part"

body = document.addObject("PartDesign::Body", "MainBody")
body.Label = "Main Body"
multi_part.addObject(body)
body_feature = body.newObject("PartDesign::Feature", "BodySolid")
body_feature.Shape = Part.makeBox(10, 10, 10)

pin = document.addObject("Part::Feature", "Pin")
pin.Label = "Pin"
pin.Shape = Part.makeCylinder(2, 12)
multi_part.addObject(pin)

plate = document.addObject("Part::Feature", "Plate")
plate.Label = "Plate"
plate.Shape = Part.makeBox(16, 4, 2)
multi_part.addObject(plate)

single_part = document.addObject("App::Part", "SinglePart")
single_part.Label = "Single-target Part"
single_body = document.addObject("PartDesign::Body", "SingleBody")
single_body.Label = "Single Body"
single_part.addObject(single_body)
single_feature = single_body.newObject("PartDesign::Feature", "SingleSolid")
single_feature.Shape = Part.makeBox(5, 5, 5)

document.recompute()
document.saveAs(output_path)
App.closeDocument(document.Name)

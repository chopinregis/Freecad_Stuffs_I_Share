#***************************************************************************
#*   Copyright (c) 2013 Yorik van Havre <yorik@uncreated.net>
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

import FreeCAD
import ArchComponent
import Draft
import DraftVecUtils

if FreeCAD.GuiUp:
    import FreeCADGui
    from draftutils.translate import translate
    from PySide import QtCore, QtGui, QtWidgets
else:
    def translate(ctxt, txt):
        return txt

__title__  = "FreeCAD Arch Frame"
__author__ = "Yorik van Havre (original) + enhancements"
__url__    = "https://www.freecad.org"


# ------------------------------------------------------------------------------
# Helper: transform a shape from one object's global coords into another's local coords
# ------------------------------------------------------------------------------
def shapeToLocal(shape, sourceObj, targetObj):
    """
    Transforms 'shape' from sourceObj's global coordinate system
    into targetObj's local coordinate system.
    If getGlobalPlacement() is unavailable, fallback to .Placement.
    """
    newShape = shape.copy()
    if hasattr(sourceObj, "getGlobalPlacement"):
        sourcePlacement = sourceObj.getGlobalPlacement()
    else:
        sourcePlacement = sourceObj.Placement
    if hasattr(targetObj, "getGlobalPlacement"):
        targetPlacement = targetObj.getGlobalPlacement()
    else:
        targetPlacement = targetObj.Placement
    newShape.Placement = sourcePlacement.multiply(targetPlacement.inverse())
    return newShape


# ------------------------------------------------------------------------------
# Parametric Frame object with AddTool and SubtractTool, plus onChanged
# ------------------------------------------------------------------------------
class _Frame(ArchComponent.Component):
    """A parametric frame object with independent alignment options on X, Y, and Z axes."""

    def __init__(self, obj):
        ArchComponent.Component.__init__(self, obj)
        self.setProperties(obj)
        obj.IfcType = "Railing"  # example IFC type

    def setProperties(self, obj):
        pl = obj.PropertiesList

        # Profile and alignment flag:
        if "Profile" not in pl:
            obj.addProperty("App::PropertyLink", "Profile", "Frame",
                            translate("App::Property", "The profile used to build this frame"))
        if "Align" not in pl:
            obj.addProperty("App::PropertyBool", "Align", "Frame",
                            translate("App::Property", "Align the profile with the extrusion edges"))
            obj.Align = True

        # Independent alignment properties (default = Center for all):
        if "AlignmentEdgeX" not in pl:
            obj.addProperty("App::PropertyEnumeration", "AlignmentEdgeX", "Alignment",
                            translate("App::Property", "Reference edge for profile alignment in X-axis"))
            obj.AlignmentEdgeX = ["Left", "Center", "Right"]
            obj.AlignmentEdgeX = "Center"
        if "OffsetDistanceX" not in pl:
            obj.addProperty("App::PropertyDistance", "OffsetDistanceX", "Alignment",
                            translate("App::Property", "Offset from X-axis reference edge (positive/relative)"))
            obj.OffsetDistanceX = 0.0
        if "AlignmentEdgeY" not in pl:
            obj.addProperty("App::PropertyEnumeration", "AlignmentEdgeY", "Alignment",
                            translate("App::Property", "Reference edge for profile alignment in Y-axis"))
            obj.AlignmentEdgeY = ["Front", "Center", "Back"]
            obj.AlignmentEdgeY = "Center"
        if "OffsetDistanceY" not in pl:
            obj.addProperty("App::PropertyDistance", "OffsetDistanceY", "Alignment",
                            translate("App::Property", "Offset from Y-axis reference edge (positive/relative)"))
            obj.OffsetDistanceY = 0.0
        if "AlignmentEdgeZ" not in pl:
            obj.addProperty("App::PropertyEnumeration", "AlignmentEdgeZ", "Alignment",
                            translate("App::Property", "Reference edge for profile alignment in Z-axis"))
            obj.AlignmentEdgeZ = ["Top", "Center", "Bottom"]
            obj.AlignmentEdgeZ = "Center"
        if "OffsetDistanceZ" not in pl:
            obj.addProperty("App::PropertyDistance", "OffsetDistanceZ", "Alignment",
                            translate("App::Property", "Offset from Z-axis reference edge (positive/relative)"))
            obj.OffsetDistanceZ = 0.0

        # Other properties:
        if "BasePoint" not in pl:
            obj.addProperty("App::PropertyInteger", "BasePoint", "Frame",
                            translate("App::Property", "Which crossing point of the path on the profile to use"))
        if "ProfilePlacement" not in pl:
            obj.addProperty("App::PropertyPlacement", "ProfilePlacement", "Frame",
                            translate("App::Property", "Additional placement for the profile before extrusion"))
        if "Rotation" not in pl:
            obj.addProperty("App::PropertyAngle", "Rotation", "Frame",
                            translate("App::Property", "Rotation of the profile around its extrusion axis"))
        if "Edges" not in pl:
            obj.addProperty("App::PropertyEnumeration", "Edges", "Frame",
                            translate("App::Property", "Edges to consider for extrusion"))
            obj.Edges = ["All edges", "Vertical edges", "Horizontal edges",
                         "Bottom horizontal edges", "Top horizontal edges"]
        if "Fuse" not in pl:
            obj.addProperty("App::PropertyBool", "Fuse", "Frame",
                            translate("App::Property", "If true, extrusions are fused into one solid"))
        if "AddTool" not in pl:
            obj.addProperty("App::PropertyLink", "AddTool", "Frame",
                            translate("App::Property", "Object to fuse (union) with the frame"))
        if "SubtractTool" not in pl:
            obj.addProperty("App::PropertyLink", "SubtractTool", "Frame",
                            translate("App::Property", "Object to cut from the frame"))

        self.Type = "Frame"

    def onChanged(self, obj, prop):
        """Handle property changes to trigger recomputes."""
        if prop in ["AddTool", "SubtractTool",
                    "AlignmentEdgeX", "OffsetDistanceX",
                    "AlignmentEdgeY", "OffsetDistanceY",
                    "AlignmentEdgeZ", "OffsetDistanceZ"]:
            obj.touch()
            obj.recompute()
        ArchComponent.Component.onChanged(self, obj, prop)

    def execute(self, obj):
        """Recompute the frame shape each time properties change."""
        import Part
        import DraftGeomUtils
        from draftgeoutils.edges import findMidpoint

        # Early checks:
        if not obj.Base or not obj.Base.Shape:
            FreeCAD.Console.PrintError("Frame: Invalid or missing Base object.\n")
            return
        if not obj.Profile or not obj.Profile.Shape:
            FreeCAD.Console.PrintError("Frame: Invalid or missing Profile object.\n")
            return

        if self.clone(obj):
            return

        baseShape    = obj.Base.Shape
        profileShape = obj.Profile.Shape
        pl           = obj.Placement
        final_shape  = None

        # Apply optional ProfilePlacement:
        if hasattr(obj, "ProfilePlacement") and not obj.ProfilePlacement.isNull():
            tempProfile = profileShape.copy()
            tempProfile.Placement = obj.ProfilePlacement.multiply(tempProfile.Placement)
            profileShape = tempProfile

        edges = baseShape.Edges
        if not edges:
            if baseShape.Solids:
                final_shape = baseShape.copy()
            else:
                FreeCAD.Console.PrintWarning("Frame: Base has no edges or solids; skipping.\n")
                return
        else:
            if not profileShape.Faces:
                wires = profileShape.Wires
                if not wires:
                    FreeCAD.Console.PrintError("Frame: Profile has no faces or wires.\n")
                    return
                face_list = []
                for w in wires:
                    if w.isClosed():
                        face_list.append(Part.Face(w))
                if len(face_list) == 1:
                    profileShape = face_list[0]
                else:
                    profileShape = Part.makeCompound(face_list)

            # Filter edges by the 'Edges' property:
            if obj.Edges == "Vertical edges":
                rv = obj.Base.Placement.Rotation.multVec(FreeCAD.Vector(0, 1, 0))
                edges = [e for e in edges if round(rv.getAngle(e.tangentAt(e.FirstParameter)), 4) in [0, 3.1416]]
            elif obj.Edges == "Horizontal edges":
                rv = obj.Base.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
                edges = [e for e in edges if round(rv.getAngle(e.tangentAt(e.FirstParameter)), 4) in [0, 3.1416]]
            elif obj.Edges == "Top horizontal edges":
                rv = obj.Base.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
                edges = [e for e in edges if round(rv.getAngle(e.tangentAt(e.FirstParameter)), 4) in [0, 3.1416]]
                edges = sorted(edges, key=lambda x: x.CenterOfMass.z, reverse=True)
                if edges:
                    topz = edges[0].CenterOfMass.z
                    edges = [e for e in edges if abs(e.CenterOfMass.z - topz) < 1e-7]
            elif obj.Edges == "Bottom horizontal edges":
                rv = obj.Base.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
                edges = [e for e in edges if round(rv.getAngle(e.tangentAt(e.FirstParameter)), 4) in [0, 3.1416]]
                edges = sorted(edges, key=lambda x: x.CenterOfMass.z)
                if edges:
                    botz = edges[0].CenterOfMass.z
                    edges = [e for e in edges if abs(e.CenterOfMass.z - botz) < 1e-7]

            shapes = []
            normal = DraftGeomUtils.getNormal(baseShape)

            for e in edges:
                bvec = DraftGeomUtils.vec(e)
                bpt  = e.Vertexes[0].Point

                profCopy = profileShape.copy()
                if obj.Align:
                    if normal is not None:
                        rot = FreeCAD.Rotation(FreeCAD.Vector(), normal, bvec, "ZYX")
                    else:
                        rot = FreeCAD.Rotation(FreeCAD.Vector(), bvec, bvec, "ZYX")
                    profCopy.Placement.Rotation = rot

                # --- Multi-Axis Independent Alignment Logic ---
                # Compute rotated basis vectors for each axis:
                unitX = rot.multVec(FreeCAD.Vector(1, 0, 0))
                unitY = rot.multVec(FreeCAD.Vector(0, 1, 0))
                unitZ = rot.multVec(FreeCAD.Vector(0, 0, 1))
                origin = profCopy.Placement.Base

                # X-axis:
                dotsX = [unitX.dot(v.Point) for v in profCopy.Vertexes]
                minX = min(dotsX)
                maxX = max(dotsX)
                centerX = unitX.dot(origin)
                if obj.AlignmentEdgeX == "Center":
                    offsetX = 0
                elif obj.AlignmentEdgeX == "Left":
                    offsetX = (minX - centerX)
                elif obj.AlignmentEdgeX == "Right":
                    offsetX = (maxX - centerX)
                else:
                    offsetX = 0
                finalOffsetX = offsetX + obj.OffsetDistanceX.Value

                # Y-axis:
                dotsY = [unitY.dot(v.Point) for v in profCopy.Vertexes]
                minY = min(dotsY)
                maxY = max(dotsY)
                centerY = unitY.dot(origin)
                if obj.AlignmentEdgeY == "Center":
                    offsetY = 0
                elif obj.AlignmentEdgeY == "Front":
                    offsetY = (minY - centerY)
                elif obj.AlignmentEdgeY == "Back":
                    offsetY = (maxY - centerY)
                else:
                    offsetY = 0
                finalOffsetY = offsetY + obj.OffsetDistanceY.Value

                # Z-axis:
                dotsZ = [unitZ.dot(v.Point) for v in profCopy.Vertexes]
                minZ = min(dotsZ)
                maxZ = max(dotsZ)
                centerZ = unitZ.dot(origin)
                if obj.AlignmentEdgeZ == "Center":
                    offsetZ = 0
                elif obj.AlignmentEdgeZ == "Top":
                    offsetZ = (maxZ - centerZ)
                elif obj.AlignmentEdgeZ == "Bottom":
                    offsetZ = (minZ - centerZ)
                else:
                    offsetZ = 0
                finalOffsetZ = offsetZ + obj.OffsetDistanceZ.Value

                # Combine offsets into one translation vector:
                translation_vector = unitX * finalOffsetX + unitY * finalOffsetY + unitZ * finalOffsetZ
                desired_point = origin + translation_vector
                delta = bpt - desired_point
                profCopy.translate(delta)
                # -------------------------------------

                if obj.Rotation:
                    profCopy.rotate(bpt, bvec, obj.Rotation)

                shapes.append(profCopy.extrude(bvec))

            if not shapes:
                return

            if obj.Fuse:
                try:
                    fused = shapes[0].multiFuse(shapes[1:])
                    fused = fused.removeSplitter()
                    if fused.isValid():
                        final_shape = fused
                    else:
                        FreeCAD.Console.PrintError("Frame: multiFuse invalid, using compound.\n")
                        final_shape = Part.makeCompound(shapes)
                except Exception as ff:
                    FreeCAD.Console.PrintError(f"Frame: multiFuse failed: {ff}\n")
                    final_shape = Part.makeCompound(shapes)
            else:
                final_shape = Part.makeCompound(shapes)

        if not final_shape:
            FreeCAD.Console.PrintWarning("Frame: No shape produced.\n")
            return

        if obj.AddTool and obj.AddTool.Shape:
            try:
                addShapeLocal = shapeToLocal(obj.AddTool.Shape, obj.AddTool, obj)
                if not addShapeLocal.isNull() and addShapeLocal.isValid():
                    fused = final_shape.fuse(addShapeLocal)
                    fused = fused.removeSplitter()
                    if fused.isValid():
                        final_shape = fused
                    else:
                        FreeCAD.Console.PrintError("AddTool: Fused shape invalid.\n")
                else:
                    FreeCAD.Console.PrintError("AddTool: Shape is null or invalid.\n")
            except Exception as e:
                FreeCAD.Console.PrintError(f"AddTool failed: {str(e)}\n")

        if obj.SubtractTool and obj.SubtractTool.Shape:
            try:
                subShapeLocal = shapeToLocal(obj.SubtractTool.Shape, obj.SubtractTool, obj)
                if not subShapeLocal.isNull() and subShapeLocal.isValid():
                    cutres = final_shape.cut(subShapeLocal)
                    if cutres.isValid():
                        final_shape = cutres
                    else:
                        FreeCAD.Console.PrintError("SubtractTool: Cut shape invalid.\n")
                else:
                    FreeCAD.Console.PrintError("SubtractTool: Shape is null or invalid.\n")
            except Exception as e:
                FreeCAD.Console.PrintError(f"SubtractTool failed: {str(e)}\n")

        obj.Shape = final_shape
        obj.Placement = pl


# ------------------------------------------------------------------------------
# View Provider for the Frame object
# ------------------------------------------------------------------------------
class _ViewProviderFrame(ArchComponent.ViewProviderComponent):
    def __init__(self, vobj):
        ArchComponent.ViewProviderComponent.__init__(self, vobj)

    def getIcon(self):
        try:
            import Arch_rc
            return ":/icons/Arch_Frame_Tree.svg"
        except ImportError:
            return None

    def claimChildren(self):
        p = []
        if hasattr(self, "Object") and self.Object:
            if self.Object.Profile:
                p.append(self.Object.Profile)
        return ArchComponent.ViewProviderComponent.claimChildren(self) + p


# ------------------------------------------------------------------------------
# Dialog: Create a Frame from Base & Profile, optionally SubtractTool
# ------------------------------------------------------------------------------
class FrameCreator:
    def __init__(self):
        self.dialog = None
        self.createDialog()

    def createDialog(self):
        self.dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
        self.dialog.setWindowTitle("Frame Creator")
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self.dialog)
        info = QtWidgets.QLabel(
            "Select a Base object (a path or solid) and a Profile.\n"
            "Optionally pick a Subtraction Tool at creation.\n"
            "After creation, you can adjust AddTool/SubtractTool and the alignment parameters in the Data tab."
        )
        layout.addWidget(info)

        self.baseCombo = QtWidgets.QComboBox()
        self.baseCombo.currentIndexChanged.connect(self.onBaseComboChange)
        layout.addWidget(QtWidgets.QLabel("Base Object:"))
        layout.addWidget(self.baseCombo)

        self.profileCombo = QtWidgets.QComboBox()
        self.profileCombo.currentIndexChanged.connect(self.onProfileComboChange)
        layout.addWidget(QtWidgets.QLabel("Profile Object:"))
        layout.addWidget(self.profileCombo)

        self.alignCheck = QtWidgets.QCheckBox("Align Profile")
        self.alignCheck.setChecked(True)
        layout.addWidget(self.alignCheck)

        self.fuseCheck = QtWidgets.QCheckBox("Fuse Extrusions")
        self.fuseCheck.setChecked(False)
        layout.addWidget(self.fuseCheck)

        # --- Independent Alignment Controls ---
        # X-axis: Left, Center, Right
        alignX_layout = QtWidgets.QHBoxLayout()
        alignX_layout.addWidget(QtWidgets.QLabel("Alignment X:"))
        self.alignXCombo = QtWidgets.QComboBox()
        self.alignXCombo.addItems(["Left", "Center", "Right"])
        self.alignXCombo.setCurrentText("Center")  # Set default
        alignX_layout.addWidget(self.alignXCombo)
        alignX_layout.addWidget(QtWidgets.QLabel("Offset X:"))
        self.offsetXSpin = QtWidgets.QDoubleSpinBox()
        self.offsetXSpin.setMinimum(-1000)
        self.offsetXSpin.setMaximum(1000)
        self.offsetXSpin.setValue(0.0)
        alignX_layout.addWidget(self.offsetXSpin)
        layout.addLayout(alignX_layout)

        # Y-axis: Front, Center, Back
        alignY_layout = QtWidgets.QHBoxLayout()
        alignY_layout.addWidget(QtWidgets.QLabel("Alignment Y:"))
        self.alignYCombo = QtWidgets.QComboBox()
        self.alignYCombo.addItems(["Front", "Center", "Back"])
        self.alignYCombo.setCurrentText("Center") 
        alignY_layout.addWidget(self.alignYCombo)
        alignY_layout.addWidget(QtWidgets.QLabel("Offset Y:"))
        self.offsetYSpin = QtWidgets.QDoubleSpinBox()
        self.offsetYSpin.setMinimum(-1000)
        self.offsetYSpin.setMaximum(1000)
        self.offsetYSpin.setValue(0.0)
        alignY_layout.addWidget(self.offsetYSpin)
        layout.addLayout(alignY_layout)

        # Z-axis: Top, Center, Bottom
        alignZ_layout = QtWidgets.QHBoxLayout()
        alignZ_layout.addWidget(QtWidgets.QLabel("Alignment Z:"))
        self.alignZCombo = QtWidgets.QComboBox()
        self.alignZCombo.addItems(["Top", "Center", "Bottom"])
        self.alignZCombo.setCurrentText("Center")
        alignZ_layout.addWidget(self.alignZCombo)
        alignZ_layout.addWidget(QtWidgets.QLabel("Offset Z:"))
        self.offsetZSpin = QtWidgets.QDoubleSpinBox()
        self.offsetZSpin.setMinimum(-1000)
        self.offsetZSpin.setMaximum(1000)
        self.offsetZSpin.setValue(0.0)
        alignZ_layout.addWidget(self.offsetZSpin)
        layout.addLayout(alignZ_layout)

        self.subtractCombo = QtWidgets.QComboBox()
        layout.addWidget(QtWidgets.QLabel("Subtraction Tool (optional):"))
        layout.addWidget(self.subtractCombo)

        layout.addStretch()

        btnLayout = QtWidgets.QHBoxLayout()
        createBtn = QtWidgets.QPushButton("Create Frame")
        createBtn.clicked.connect(self.createFrame)
        cancelBtn = QtWidgets.QPushButton("Cancel")
        cancelBtn.clicked.connect(self.dialog.reject)
        btnLayout.addWidget(createBtn)
        btnLayout.addWidget(cancelBtn)
        layout.addLayout(btnLayout)

        self.populateComboBoxes()

    def populateComboBoxes(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            FreeCAD.Console.PrintError("No active document found.\n")
            return
        self.baseCombo.addItem(" -- None -- ")
        self.profileCombo.addItem(" -- None -- ")
        self.subtractCombo.addItem(" -- None -- ")
        for obj in doc.Objects:
            self.baseCombo.addItem(obj.Name)
            self.profileCombo.addItem(obj.Name)
            self.subtractCombo.addItem(obj.Name)

    def onBaseComboChange(self, idx):
        name = self.baseCombo.itemText(idx)
        if not name.startswith(" --"):
            obj = FreeCAD.ActiveDocument.getObject(name)
            if obj:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(obj)

    def onProfileComboChange(self, idx):
        name = self.profileCombo.itemText(idx)
        if not name.startswith(" --"):
            obj = FreeCAD.ActiveDocument.getObject(name)
            if obj:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(obj)

    def createFrame(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            QtWidgets.QMessageBox.critical(self.dialog, "Error", "No active document.")
            return
        baseName     = self.baseCombo.currentText()
        profileName  = self.profileCombo.currentText()
        subtractName = self.subtractCombo.currentText()
        if baseName.startswith(" --") or profileName.startswith(" --"):
            QtWidgets.QMessageBox.critical(self.dialog, "Error", "Please select valid Base and Profile objects.")
            return
        baseObj = doc.getObject(baseName)
        profObj = doc.getObject(profileName)
        subObj  = doc.getObject(subtractName) if not subtractName.startswith(" --") else None
        if not baseObj or not profObj:
            QtWidgets.QMessageBox.critical(self.dialog, "Error", "Unable to retrieve the selected objects.")
            return
        try:
            frameObj = doc.addObject("Part::FeaturePython", "Frame")
            _Frame(frameObj)
            _ViewProviderFrame(frameObj.ViewObject)
            frameObj.Base    = baseObj
            frameObj.Profile = profObj
            frameObj.Align   = self.alignCheck.isChecked()
            frameObj.Fuse    = self.fuseCheck.isChecked()
            frameObj.AlignmentEdgeX = self.alignXCombo.currentText()
            frameObj.OffsetDistanceX = self.offsetXSpin.value()
            frameObj.AlignmentEdgeY = self.alignYCombo.currentText()
            frameObj.OffsetDistanceY = self.offsetYSpin.value()
            frameObj.AlignmentEdgeZ = self.alignZCombo.currentText()
            frameObj.OffsetDistanceZ = self.offsetZSpin.value()
            if subObj:
                frameObj.SubtractTool = subObj
            frameObj.recompute()
            doc.recompute()
            self.dialog.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.dialog, "Error", str(e))
            FreeCAD.Console.PrintError(f"Error creating frame: {e}\n")


# ------------------------------------------------------------------------------
# Macro Execution
# ------------------------------------------------------------------------------
if FreeCAD.GuiUp:
    creator = FrameCreator()
    creator.dialog.exec_()
else:
    FreeCAD.Console.PrintError("This macro requires the FreeCAD GUI.\n")

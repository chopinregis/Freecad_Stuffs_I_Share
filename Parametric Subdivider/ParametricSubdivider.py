import FreeCAD, FreeCADGui, Part, Draft
from PySide2 import QtCore, QtGui, QtWidgets
import math

##########################################################
# Global Helper Function: Clip a Line to a Face (or planar shape)
##########################################################
def clip_line_to_face(line, face):
    """
    Returns a list of edges representing the portion(s) of the input line
    that lie within the given face. Uses the face's common() method to
    intersect the line's wire with the face.
    """
    try:
        line_wire = Part.Wire([line])
        common = face.common(line_wire)
        if common.Edges:
            return common.Edges
        return []
    except Exception as e:
        FreeCAD.Console.PrintWarning("Clipping error: {}.\n".format(str(e)))
        return [line]

##########################################################
# Custom Double Spin Box Supporting Imperial Input
##########################################################
class CustomDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(CustomDoubleSpinBox, self).__init__(*args, **kwargs)
        self.imperial = False

    def setImperial(self, flag: bool):
        self.imperial = flag
        self.lineEdit().setText(self.textFromValue(self.value()))

    def validate(self, text, pos):
        return (QtGui.QValidator.Acceptable, text, pos)

    def valueFromText(self, text):
        if self.imperial:
            s = self.cleanText().strip().lower()
            if s == "":
                return 0.0
            feet = 0.0
            inches = 0.0
            if "ft" in s:
                parts = s.split("ft")
                try:
                    feet = float(parts[0].strip())
                except:
                    feet = 0.0
                remainder = parts[1].strip() if len(parts) > 1 else ""
                if "in" in remainder:
                    try:
                        inches = float(remainder.split("in")[0].strip())
                    except:
                        inches = 0.0
                elif remainder:
                    try:
                        inches = float(remainder)
                    except:
                        inches = 0.0
            elif "in" in s:
                try:
                    inches = float(s.split("in")[0].strip())
                except:
                    inches = 0.0
            elif "'" in s:
                parts = s.split("'")
                try:
                    feet = float(parts[0].strip())
                except:
                    feet = 0.0
                if len(parts) > 1:
                    in_str = parts[1].replace('"', '').strip()
                    if in_str:
                        if " " in in_str:
                            subparts = in_str.split()
                            try:
                                inches = float(subparts[0])
                            except:
                                inches = 0.0
                            if len(subparts) > 1:
                                frac_part = subparts[1]
                                try:
                                    num, den = frac_part.split('/')
                                    inches += float(num) / float(den)
                                except:
                                    pass
                        else:
                            try:
                                inches = float(in_str)
                            except:
                                if "/" in in_str:
                                    try:
                                        num, den = in_str.split('/')
                                        inches = float(num) / float(den)
                                    except:
                                        inches = 0.0
                                else:
                                    inches = 0.0
            else:
                try:
                    inches = float(s.replace('"', ''))
                except:
                    inches = 0.0
            return feet * 12.0 + inches
        else:
            return super(CustomDoubleSpinBox, self).valueFromText(text)

    def textFromValue(self, value):
        if self.imperial:
            total_inches = value
            feet = int(total_inches // 12)
            inches = total_inches - feet * 12
            quarter = round(inches * 4) / 4.0
            if quarter >= 12:
                feet += 1
                quarter = 0.0
            int_inch = int(quarter)
            frac = quarter - int_inch
            frac_str = ""
            if abs(frac - 0.25) < 1e-3:
                frac_str = " 1/4"
            elif abs(frac - 0.5) < 1e-3:
                frac_str = " 1/2"
            elif abs(frac - 0.75) < 1e-3:
                frac_str = " 3/4"
            elif abs(frac) < 1e-3:
                frac_str = ""
            else:
                frac_str = f" {frac:.2f}"
            if feet > 0:
                return f"{feet}' {int_inch}{frac_str}\"".strip()
            else:
                return f"{int_inch}{frac_str}\"".strip()
        else:
            return super(CustomDoubleSpinBox, self).textFromValue(value)

##########################################################
# Custom Property Editor for SubdivisionPattern (Data Tab)
##########################################################
class SubdivisionPropertyEditor(QtWidgets.QWidget):
    def __init__(self, feature, parent=None):
        super(SubdivisionPropertyEditor, self).__init__(parent)
        self.feature = feature
        layout = QtWidgets.QFormLayout(self)

        # Local UI unit mode (default mm)
        currentUnit = "mm"
        self.localUnit = currentUnit

        # --- Spacing Mode Row ---
        self.spacing_mode_combo = QtWidgets.QComboBox()
        self.spacing_mode_combo.addItems(["Absolute Spacing", "Quantity Divisions"])
        self.spacing_mode_combo.setCurrentText(feature.SpacingMode)
        layout.addRow("Spacing Mode:", self.spacing_mode_combo)

        self.unitCombo = QtWidgets.QComboBox()
        self.unitCombo.addItems(["mm", "inches"])
        self.unitCombo.setCurrentText(currentUnit)
        layout.addRow("Units:", self.unitCombo)

        # Primary spacing spin
        self.primarySpin = CustomDoubleSpinBox()
        self.primarySpin.setRange(0.001, 10000)
        if currentUnit == "inches":
            self.primarySpin.setValue(feature.PrimarySpacing / 25.4)
        else:
            self.primarySpin.setValue(500.0)  # Set default to 500 mm

        # Divisions spin
        self.divisions_spin = QtWidgets.QSpinBox()
        self.divisions_spin.setRange(1, 10000)
        self.divisions_spin.setValue(10)  # Set default to 10 divisions
        self.primaryLabel = QtWidgets.QLabel("Primary Spacing (mm):")
        layout.addRow(self.primaryLabel, self.primarySpin)

        # Divisions spin
        self.divisions_spin = QtWidgets.QSpinBox()
        self.divisions_spin.setRange(1, 10000)
        self.divisions_spin.setValue(feature.Divisions)
        layout.addRow("Divisions:", self.divisions_spin)

        # Start Offset
        self.offsetSpin = CustomDoubleSpinBox()
        self.offsetSpin.setRange(-10000, 10000)
        if currentUnit == "inches":
            self.offsetSpin.setValue(feature.StartOffset / 25.4)
        else:
            self.offsetSpin.setValue(feature.StartOffset)
        self.offsetLabel = QtWidgets.QLabel("Start Offset (mm):")
        layout.addRow(self.offsetLabel, self.offsetSpin)

        # --- Independent Crosshatch Spacing ---
        self.hSpacingSpin = CustomDoubleSpinBox()
        self.hSpacingSpin.setRange(0.001, 10000)
        self.hSpacingSpin.setValue(feature.HorizontalSpacing)
        self.hSpacingLabel = QtWidgets.QLabel("Horizontal Spacing (mm):")
        layout.addRow(self.hSpacingLabel, self.hSpacingSpin)

        self.vSpacingSpin = CustomDoubleSpinBox()
        self.vSpacingSpin.setRange(0.001, 10000)
        self.vSpacingSpin.setValue(feature.VerticalSpacing)
        self.vSpacingLabel = QtWidgets.QLabel("Vertical Spacing (mm):")
        layout.addRow(self.vSpacingLabel, self.vSpacingSpin)

        # Linked Spacing
        self.linkedCheck = QtWidgets.QCheckBox("Linked Spacing")
        self.linkedCheck.setChecked(feature.LinkedSpacing)
        layout.addRow(self.linkedCheck)

        # Clip Offset controls
        clip_group = QtWidgets.QGroupBox("Clip Offset")
        clip_layout = QtWidgets.QHBoxLayout()
        self.clip_offset_check = QtWidgets.QCheckBox("Enable")
        self.clip_offset_check.setChecked(feature.UseClipOffset)
        self.clip_offset_field = CustomDoubleSpinBox()
        self.clip_offset_field.setRange(0.0, 10000)
        self.clip_offset_field.setValue(feature.ClipOffset)
        clip_layout.addWidget(self.clip_offset_check)
        clip_layout.addWidget(QtWidgets.QLabel("Offset:"))
        clip_layout.addWidget(self.clip_offset_field)
        clip_group.setLayout(clip_layout)
        layout.addRow(clip_group)

        # --- Advanced Options ---
        advanced_group = QtWidgets.QGroupBox("Advanced Options")
        adv_layout = QtWidgets.QFormLayout()

        self.diagonal_angle_spin = QtWidgets.QDoubleSpinBox()
        self.diagonal_angle_spin.setRange(0,360)
        self.diagonal_angle_spin.setValue(feature.DiagonalAngle)
        self.diagonal_angle_spin.setSuffix(" °")
        adv_layout.addRow("Diagonal Angle:", self.diagonal_angle_spin)

        self.alternate_angle_check = QtWidgets.QCheckBox("Use Alternate Angle")
        self.alternate_angle_check.setChecked(feature.UseAlternateAngle)
        adv_layout.addRow(self.alternate_angle_check)

        self.alternate_angle_spin = QtWidgets.QDoubleSpinBox()
        self.alternate_angle_spin.setRange(-360,360)
        self.alternate_angle_spin.setValue(feature.AlternateAngle)
        self.alternate_angle_spin.setSuffix(" °")
        adv_layout.addRow("Alternate Angle:", self.alternate_angle_spin)

        self.stagger_offset_spin = CustomDoubleSpinBox()
        self.stagger_offset_spin.setRange(-10000,10000)
        self.stagger_offset_spin.setValue(feature.StaggerOffset)
        self.stagger_offset_spin.setSuffix(" mm")
        adv_layout.addRow("Stagger Offset:", self.stagger_offset_spin)

        self.stagger_direction_combo = QtWidgets.QComboBox()
        self.stagger_direction_combo.addItems(["Horizontal", "Vertical"])
        self.stagger_direction_combo.setCurrentText(feature.StaggerDirection)
        adv_layout.addRow("Stagger Direction:", self.stagger_direction_combo)

        self.pattern_seq_edit = QtWidgets.QLineEdit()
        self.pattern_seq_edit.setText(feature.PatternSequence)
        adv_layout.addRow("Pattern Sequence:", self.pattern_seq_edit)

        self.pattern_repeat_spin = QtWidgets.QSpinBox()
        self.pattern_repeat_spin.setRange(1, 1000)
        self.pattern_repeat_spin.setValue(feature.PatternRepeat)
        adv_layout.addRow("Pattern Repeat:", self.pattern_repeat_spin)

        advanced_group.setLayout(adv_layout)
        layout.addRow(advanced_group)

        # --- Flip Options ---
        flip_group = QtWidgets.QGroupBox("Flip Options")
        self.fuseCheck = QtWidgets.QCheckBox("Fuse Subdivisions")
        self.fuseCheck.setChecked(feature.Fuse)
        layout.addRow(self.fuseCheck)
        flip_layout = QtWidgets.QHBoxLayout()
        self.flipHCheck = QtWidgets.QCheckBox("Flip Horizontal")
        self.flipVCheck = QtWidgets.QCheckBox("Flip Vertical")
        self.flipHCheck.setChecked(feature.FlipHorizontal)
        self.flipVCheck.setChecked(feature.FlipVertical)
        flip_layout.addWidget(self.flipHCheck)
        flip_layout.addWidget(self.flipVCheck)
        flip_group.setLayout(flip_layout)
        layout.addRow(flip_group)

        # Connect signals
        self.unitCombo.currentTextChanged.connect(self.unitChanged)
        self.primarySpin.editingFinished.connect(self.updateFeature)
        self.divisions_spin.valueChanged.connect(self.updateFeature)
        self.offsetSpin.editingFinished.connect(self.updateFeature)
        self.clip_offset_check.stateChanged.connect(self.updateFeature)
        self.clip_offset_field.editingFinished.connect(self.updateFeature)
        self.diagonal_angle_spin.editingFinished.connect(self.updateFeature)
        self.alternate_angle_check.stateChanged.connect(self.updateFeature)
        self.alternate_angle_spin.editingFinished.connect(self.updateFeature)
        self.stagger_offset_spin.editingFinished.connect(self.updateFeature)
        self.stagger_direction_combo.currentTextChanged.connect(self.updateFeature)
        self.spacing_mode_combo.currentTextChanged.connect(self.updateFeature)
        self.linkedCheck.stateChanged.connect(self.updateFeature)
        self.hSpacingSpin.editingFinished.connect(self.updateFeature)
        self.vSpacingSpin.editingFinished.connect(self.updateFeature)
        self.pattern_seq_edit.editingFinished.connect(self.updateFeature)
        self.pattern_repeat_spin.valueChanged.connect(self.updateFeature)

        # Connect flip signals
        self.flipHCheck.stateChanged.connect(self.updateFeature)
        self.flipVCheck.stateChanged.connect(self.updateFeature)
        self.fuseCheck.stateChanged.connect(self.updateFeature)

        self.setLayout(layout)
        self.applyUnitSettings(currentUnit)


    def applyUnitSettings(self, unit):
        if unit == "inches":
            self.primarySpin.setImperial(True)
            self.offsetSpin.setImperial(True)
            self.clip_offset_field.setImperial(True)
            self.hSpacingSpin.setImperial(True)
            self.vSpacingSpin.setImperial(True)
            self.stagger_offset_spin.setImperial(True)

            self.primarySpin.setSuffix(" in")
            self.offsetSpin.setSuffix(" in")
            self.clip_offset_field.setSuffix(" in")
            self.hSpacingSpin.setSuffix(" in")
            self.vSpacingSpin.setSuffix(" in")
            self.stagger_offset_spin.setSuffix(" in")
        else:
            self.primarySpin.setImperial(False)
            self.offsetSpin.setImperial(False)
            self.clip_offset_field.setImperial(False)
            self.hSpacingSpin.setImperial(False)
            self.vSpacingSpin.setImperial(False)
            self.stagger_offset_spin.setImperial(False)

            self.primarySpin.setSuffix(" mm")
            self.offsetSpin.setSuffix(" mm")
            self.clip_offset_field.setSuffix(" mm")
            self.hSpacingSpin.setSuffix(" mm")
            self.vSpacingSpin.setSuffix(" mm")
            self.stagger_offset_spin.setSuffix(" mm")

    def unitChanged(self, newUnit):
        if newUnit == "inches":
            # Convert existing mm values to inches for display
            self.primarySpin.setValue(self.feature.PrimarySpacing / 25.4)
            self.offsetSpin.setValue(self.feature.StartOffset / 25.4)
            self.clip_offset_field.setValue(self.feature.ClipOffset / 25.4)
            self.hSpacingSpin.setValue(self.feature.HorizontalSpacing / 25.4)
            self.vSpacingSpin.setValue(self.feature.VerticalSpacing / 25.4)
            self.stagger_offset_spin.setValue(self.feature.StaggerOffset / 25.4)
            # Handle PatternSequence conversion (mm to inches)
            if self.feature.PatternSequence:
                try:
                    mm_values = [float(x) for x in self.feature.PatternSequence.split(",")]
                    inch_values = [v / 25.4 for v in mm_values]
                    self.pattern_seq_edit.setText(", ".join(f"{x:.3f}" for x in inch_values))
                except:
                    pass  # Handle invalid entries gracefully
        else:
            # Display mm values directly
            self.primarySpin.setValue(self.feature.PrimarySpacing)
            self.offsetSpin.setValue(self.feature.StartOffset)
            self.clip_offset_field.setValue(self.feature.ClipOffset)
            self.hSpacingSpin.setValue(self.feature.HorizontalSpacing)
            self.vSpacingSpin.setValue(self.feature.VerticalSpacing)
            self.stagger_offset_spin.setValue(self.feature.StaggerOffset)
            # Handle PatternSequence display (mm values as-is)
            if self.feature.PatternSequence:
                try:
                    mm_values = [float(x) for x in self.feature.PatternSequence.split(",")]
                    self.pattern_seq_edit.setText(", ".join(f"{x:.3f}" for x in mm_values))
                except:
                    pass  # Handle invalid entries gracefully
        self.applyUnitSettings(newUnit)
        self.localUnit = newUnit
        self.updateFeature()

    def updateFeature(self):
        # --- Update Linked Spacing Fields ---
        alignment = self.feature.AlignmentMode
        self.offsetSpin.setEnabled(alignment == "Edge-to-Edge")
        if self.linkedCheck.isChecked():
            self.hSpacingSpin.setEnabled(False)
            self.vSpacingSpin.setEnabled(False)
            self.hSpacingSpin.setToolTip("Horizontal and Vertical spacing are synced.")
            self.vSpacingSpin.setToolTip("Horizontal and Vertical spacing are synced.")
        else:
            self.hSpacingSpin.setEnabled(True)
            self.vSpacingSpin.setEnabled(True)
            self.hSpacingSpin.setToolTip("")
            self.vSpacingSpin.setToolTip("")

        # If spacing is linked, force the vertical spacing value to match the horizontal
        if self.linkedCheck.isChecked():
            self.vSpacingSpin.blockSignals(True)
            self.vSpacingSpin.setValue(self.hSpacingSpin.value())
            self.vSpacingSpin.blockSignals(False)

        # Convert values if local units are inches
        if self.localUnit == "inches":
            spacing = self.primarySpin.value() * 25.4
            offset = self.offsetSpin.value() * 25.4
            clip = self.clip_offset_field.value() * 25.4
            hspace = self.hSpacingSpin.value() * 25.4
            vspace = self.vSpacingSpin.value() * 25.4
            stagger = self.stagger_offset_spin.value() * 25.4
        else:
            spacing = self.primarySpin.value()
            offset = self.offsetSpin.value()
            clip = self.clip_offset_field.value()
            hspace = self.hSpacingSpin.value()
            vspace = self.vSpacingSpin.value()
            stagger = self.stagger_offset_spin.value()

        # Update the feature object with current values
        self.feature.SpacingMode = self.spacing_mode_combo.currentText()
        self.feature.PrimarySpacing = spacing
        self.feature.Divisions = self.divisions_spin.value()
        self.feature.StartOffset = offset
        self.feature.ClipOffset = clip
        self.feature.UseClipOffset = self.clip_offset_check.isChecked()

        self.feature.HorizontalSpacing = hspace
        self.feature.VerticalSpacing = vspace
        self.feature.LinkedSpacing = self.linkedCheck.isChecked()

        self.feature.DiagonalAngle = self.diagonal_angle_spin.value()
        self.feature.UseAlternateAngle = self.alternate_angle_check.isChecked()
        self.feature.AlternateAngle = self.alternate_angle_spin.value()
        self.feature.StaggerOffset = stagger
        self.feature.StaggerDirection = self.stagger_direction_combo.currentText()

        # Convert PatternSequence based on current unit
        pattern_text = self.pattern_seq_edit.text()
        if pattern_text.strip():
            try:
                raw_values = [float(x.strip()) for x in pattern_text.split(",") if x.strip()]
                if self.localUnit == "inches":
                    raw_values = [v * 25.4 for v in raw_values]
                self.feature.PatternSequence = ",".join(map(str, raw_values))
            except:
                self.feature.PatternSequence = pattern_text
        else:
            self.feature.PatternSequence = ""
        self.feature.PatternRepeat = self.pattern_repeat_spin.value()

        # --- Flip assignments (new) ---
        self.feature.FlipHorizontal = self.flipHCheck.isChecked()
        self.feature.FlipVertical   = self.flipVCheck.isChecked()

        self.feature.recompute()



##########################################################
# View Provider for SubdivisionPattern
##########################################################
class ViewProviderSubdivisionPattern:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.Object = obj.Object

    def getDisplayModes(self, obj):
        return ["Wireframe"]

    def getDefaultDisplayMode(self):
        return "Wireframe"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, fp, prop):
        pass

    def onChanged(self, vp, prop):
        pass

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def doubleClicked(self, vobj):
        dlg = SubdivisionDialog([(vobj.Object.BaseFace[0], vobj.Object.BaseFace[1][0])])
        dlg.featureToEdit = vobj.Object
        dlg.exec_()
        return True

    def getCustomPropertyEditor(self):
        return SubdivisionPropertyEditor(self.Object)

##########################################################
# FeaturePython Object: SubdivisionPattern
##########################################################
class SubdivisionPattern:
    """
    A FeaturePython object that creates a parametric subdivision pattern on a face.
    """
    def __init__(self, obj):
        obj.addProperty("App::PropertyLinkSub", "BaseFace", "Subdivision", "Base face for subdivision").BaseFace = None
        obj.addProperty("App::PropertyLength", "PrimarySpacing", "Subdivision", "Primary spacing value").PrimarySpacing = 500.0
        obj.addProperty("App::PropertyInteger", "Divisions", "Subdivision", "Number of divisions (if quantity mode)").Divisions = 10
        obj.addProperty("App::PropertyFloat", "RotationAngle", "Subdivision", "Rotation angle in degrees").RotationAngle = 0.0
        obj.addProperty("App::PropertyVector", "RotationAxis", "Subdivision", "Rotation axis").RotationAxis = FreeCAD.Vector(0,0,1)
        obj.addProperty("App::PropertyLength", "StartOffset", "Subdivision", "Custom start offset").StartOffset = 0.0

        obj.addProperty("App::PropertyEnumeration", "SpacingMode", "Subdivision", "Spacing mode")
        obj.SpacingMode = ["Absolute Spacing", "Quantity Divisions"]

        obj.addProperty("App::PropertyEnumeration", "SubdivisionMode", "Subdivision", "Subdivision mode")
        obj.SubdivisionMode = ["Horizontal", "Vertical", "Crosshatch", "Diagonal/Herringbone", "Staggered/Offset Grid"]

        obj.addProperty("App::PropertyEnumeration", "AlignmentMode", "Subdivision", "Alignment mode")
        obj.AlignmentMode = ["Edge-to-Edge", "Center-outward"]

        obj.addProperty("App::PropertyBool", "UseClipOffset", "Clip", "Enable clip offset").UseClipOffset = False
        obj.addProperty("App::PropertyLength", "ClipOffset", "Clip", "Offset distance").ClipOffset = 0.0

        obj.addProperty("App::PropertyFloat", "DiagonalAngle", "Subdivision", "Diagonal angle in degrees").DiagonalAngle = 45.0
        obj.addProperty("App::PropertyBool", "UseAlternateAngle", "Subdivision", "Toggle alternate angle for Diagonal/Herringbone mode").UseAlternateAngle = False
        obj.addProperty("App::PropertyFloat", "AlternateAngle", "Subdivision", "Alternate angle in degrees").AlternateAngle = -45.0

        obj.addProperty("App::PropertyLength", "StaggerOffset", "Subdivision", "Offset distance for staggered grid").StaggerOffset = 2.0
        obj.addProperty("App::PropertyEnumeration", "StaggerDirection", "Subdivision", "Stagger direction")
        obj.StaggerDirection = ["Horizontal", "Vertical"]

        # Crosshatch independent spacing
        obj.addProperty("App::PropertyLength", "HorizontalSpacing", "Subdivision", "Horizontal spacing for crosshatch").HorizontalSpacing = 50.0
        obj.addProperty("App::PropertyLength", "VerticalSpacing", "Subdivision", "Vertical spacing for crosshatch").VerticalSpacing = 50.0
        obj.addProperty("App::PropertyBool", "LinkedSpacing", "Subdivision", "Sync horizontal/vertical").LinkedSpacing = True

        # Reference line (not used in this demo)
        obj.addProperty("App::PropertyLinkSub", "ReferenceLine", "Reference", "Edge used to define rotation angle").ReferenceLine = None

        # Alternating Patterns
        obj.addProperty("App::PropertyString", "PatternSequence", "Advanced", "Comma-separated spacing for repeating pattern").PatternSequence = ""
        obj.addProperty("App::PropertyInteger", "PatternRepeat", "Advanced", "Repeat count for pattern sequence").PatternRepeat = 1

        # Flip
        obj.addProperty("App::PropertyBool", "FlipHorizontal", "Display", "Flip along horizontal axis").FlipHorizontal = False
        obj.addProperty("App::PropertyBool", "FlipVertical", "Display", "Flip along vertical axis").FlipVertical = False

        obj.addProperty(
            "App::PropertyBool",
            "UsePatternSequence",
            "Advanced",
            "Toggle whether to apply the pattern sequence"
        ).UsePatternSequence = False

        # Fuse
        obj.addProperty("App::PropertyBool", "Fuse", "Display", "Fuse subdivisions into a single shape").Fuse = False

        obj.Proxy = self

    def onChanged(self, fp, prop):
        if prop in [
            "PrimarySpacing", "Divisions", "RotationAngle", "RotationAxis",
            "StartOffset", "SpacingMode", "SubdivisionMode", "AlignmentMode",
            "UseClipOffset", "ClipOffset", "DiagonalAngle", "UseAlternateAngle",
            "AlternateAngle", "StaggerOffset", "StaggerDirection",
            "HorizontalSpacing", "VerticalSpacing", "LinkedSpacing",
            "ReferenceLine", "PatternSequence", "PatternRepeat", "BaseFace",
            "FlipHorizontal", "FlipVertical"   # <-- Added flip properties here
        ]:
            fp.recompute()


    def execute(self, obj):
        """
        A typical SubdivisionPattern.execute(...) method with the new 'UsePatternSequence' logic.
        This matches the original code structure, plus the lines labeled "# <-- NEW".
        """

        # 1) Check for valid BaseFace
        if obj.BaseFace is None:
            FreeCAD.Console.PrintError("No base face defined.\n")
            obj.Shape = Part.Compound([])
            return

        try:
            doc_obj, sub_names = obj.BaseFace
        except Exception as e:
            FreeCAD.Console.PrintError("BaseFace property malformed.\n")
            obj.Shape = Part.Compound([])
            return

        if not sub_names:
            FreeCAD.Console.PrintError("No base face sub-element.\n")
            obj.Shape = Part.Compound([])
            return

        try:
            face = doc_obj.Shape.getElement(sub_names[0])
        except:
            FreeCAD.Console.PrintError("Could not find the linked face.\n")
            obj.Shape = Part.Compound([])
            return

        # 2) Optional: Override RotationAngle using ReferenceLine if set
        if obj.ReferenceLine and obj.ReferenceLine[1]:
            try:
                ref_obj, ref_sub = obj.ReferenceLine
                edge = ref_obj.Shape.getElement(ref_sub[0])
                if hasattr(edge, "Vertexes") and len(edge.Vertexes) == 2:
                    p1 = edge.Vertexes[0].Point
                    p2 = edge.Vertexes[1].Point
                    edge_dir = (p2 - p1)
                    edge_dir.normalize()
                    nrm = face.normalAt(0, 0)
                    arbitrary = FreeCAD.Vector(0, 0, 1)
                    if abs(nrm.dot(arbitrary)) > 0.99:
                        arbitrary = FreeCAD.Vector(1, 0, 0)
                    t = arbitrary.cross(nrm).normalize()
                    angle = math.degrees(t.getAngle(edge_dir))
                    obj.RotationAngle = angle
            except Exception as e:
                FreeCAD.Console.PrintWarning("Reference line angle computation failed: {}.\n".format(e))

        # 3) Construct local coordinate system (same as your original code)
        center = face.CenterOfMass
        nrm = face.normalAt(0, 0)
        arbitrary = FreeCAD.Vector(0, 0, 1)
        if abs(nrm.dot(arbitrary)) > 0.99:
            arbitrary = FreeCAD.Vector(1, 0, 0)
        t = arbitrary.cross(nrm)
        t.normalize()
        b = nrm.cross(t)
        b.normalize()
        localPl = FreeCAD.Placement(center, FreeCAD.Rotation(t, b, nrm))
        T_inv = localPl.inverse()

        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        diagonal = math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        extension = 2 * diagonal

        # 4) Read your subdivision parameters from the object
        spacing_mode = obj.SpacingMode   # "Absolute Spacing" or "Quantity Divisions"
        division_count = obj.Divisions
        primary       = float(obj.PrimarySpacing)
        start         = float(obj.StartOffset)
        mode          = obj.SubdivisionMode
        alignment     = obj.AlignmentMode
        rotation_deg  = float(obj.RotationAngle)
        horiz_spacing = float(obj.HorizontalSpacing)
        vert_spacing  = float(obj.VerticalSpacing)

        # ----------------------------------------------------------------------
        # 5) **NEW**: Decide whether to use pattern, based on UsePatternSequence
        # ----------------------------------------------------------------------
        pattern_list = []
        if getattr(obj, "UsePatternSequence", False):  # <-- NEW: Check the new property
            # If True, parse PatternSequence
            pattern_text = obj.PatternSequence.strip()
            if pattern_text:
                try:
                    raw_list = [abs(float(x)) for x in pattern_text.split(",") if x.strip()]
                    pattern_list = raw_list
                except Exception as e:
                    FreeCAD.Console.PrintWarning("Failed to parse PatternSequence.\n")
                    pattern_list = []
        # If UsePatternSequence == False, pattern_list stays empty, ignoring pattern logic

        # 6) Build lines based on SubdivisionMode
        lines = []
        if mode == "Horizontal":
            lines = self.buildHorizontalPattern(obj, face, localPl, pattern_list, patternRepeat=obj.PatternRepeat)
        elif mode == "Vertical":
            lines = self.buildVerticalPattern(obj, face, localPl, pattern_list, patternRepeat=obj.PatternRepeat)
        elif mode == "Crosshatch":
            lines = self.buildCrosshatch(obj, face, localPl, pattern_list, patternRepeat=obj.PatternRepeat)
        elif mode == "Diagonal/Herringbone":
            lines = self.buildDiagonalPattern(obj, face, localPl, pattern_list, patternRepeat=obj.PatternRepeat)
        elif mode == "Staggered/Offset Grid":
            lines = self.buildStaggeredPattern(obj, face, localPl)
        else:
            FreeCAD.Console.PrintError("Unsupported subdivision mode: {}\n".format(mode))
            obj.Shape = Part.Compound([])
            return

        # 7) Handle Flip if needed
        if lines and (obj.FlipHorizontal or obj.FlipVertical):
            centerLocal = localPl.inverse().multVec(face.CenterOfMass)
            for i, edge in enumerate(lines):
                v1_local = T_inv.multVec(edge.Vertexes[0].Point)
                v2_local = T_inv.multVec(edge.Vertexes[1].Point)
                if obj.FlipHorizontal:
                    v1_local.x = 2 * centerLocal.x - v1_local.x
                    v2_local.x = 2 * centerLocal.x - v2_local.x
                if obj.FlipVertical:
                    v1_local.y = 2 * centerLocal.y - v1_local.y
                    v2_local.y = 2 * centerLocal.y - v2_local.y
                new_start = localPl.multVec(v1_local)
                new_end   = localPl.multVec(v2_local)
                lines[i]  = Part.makeLine(new_start, new_end)

        # 8) Apply ClipOffset if enabled
        if lines and obj.UseClipOffset and float(obj.ClipOffset) != 0:
            offset_value = -float(obj.ClipOffset) if obj.ClipOffset > 0 else abs(obj.ClipOffset)
            try:
                outer_wire = face.OuterWire
                offset_wire = outer_wire.makeOffset2D(offset_value)
                offset_face = Part.Face(offset_wire)
            except Exception as e:
                FreeCAD.Console.PrintWarning("Clip offset failed: {}.\n".format(e))
                offset_face = None

            if offset_face:
                new_lines = []
                for edge in lines:
                    new_lines.extend(clip_line_to_face(edge, offset_face))
                if new_lines:
                    lines = new_lines

        # 9) Combine lines into a Part.Compound or empty if none
        if lines:
            wires = [Part.Wire(e) for e in lines]
            if obj.Fuse:  # <-- NEW: Fuse if enabled using an iterative approach
                fused_shape = wires[0]
                for w in wires[1:]:
                    fused_shape = fused_shape.fuse(w)
                obj.Shape = fused_shape.removeSplitter()
            else:
                obj.Shape = Part.Compound(wires)
        else:
            obj.Shape = Part.Compound([])
        return


    # Below are helper methods (buildHorizontalPattern, buildVerticalPattern, etc.)
    # ... [For brevity, these methods are unchanged from your version] ...
    # (Include the unchanged buildHorizontalPattern, buildVerticalPattern,
    # buildCrosshatch, buildDiagonalPattern, and buildStaggeredPattern methods here)
    # For the complete script, please paste in your original implementations.
    # (They remain the same as in your provided script.)
    def buildHorizontalPattern(self, obj, face, localPl, pattern_list, patternRepeat=1):
        # [Implementation unchanged]
        T_inv = localPl.inverse()
        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        extension = 2 * math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        alignment = obj.AlignmentMode
        spacing_mode = obj.SpacingMode
        start = float(obj.StartOffset)
        primary = float(obj.PrimarySpacing)
        division_count = obj.Divisions
        rotation_deg = float(obj.RotationAngle)
        lines = []
        if pattern_list:
            current_x = min_x + start
            maxLen = max_x
            seq_index = 0
            while current_x <= maxLen + 1e-9:
                start_local = FreeCAD.Vector(current_x, min_y - extension, 0)
                end_local = FreeCAD.Vector(current_x, max_y + extension, 0)
                if abs(rotation_deg) > 1e-9:
                    center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
                    rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
                    start_local = rot_local.multVec(start_local - center_local) + center_local
                    end_local = rot_local.multVec(end_local - center_local) + center_local
                global_start = localPl.multVec(start_local)
                global_end = localPl.multVec(end_local)
                line = Part.makeLine(global_start, global_end)
                lines.extend(clip_line_to_face(line, face))
                step = pattern_list[seq_index % len(pattern_list)]
                seq_index += 1
                if seq_index >= len(pattern_list):
                    patternRepeat -= 1
                    if patternRepeat <= 0:
                        break
                current_x += step
            return lines
        def safe_div(a, b):
            return a / b if abs(b) > 1e-6 else 0
        if alignment == "Center-outward":
            total_length = max_x - min_x
            center_x = (min_x + max_x) / 2
            if spacing_mode == "Absolute Spacing":
                n_val = int(safe_div(total_length / 2, primary)) if primary else 0
                count = 2 * n_val + 1
                spacing = primary
                min_val = center_x - n_val * spacing
            else:
                count = division_count if division_count > 1 else 1
                spacing = safe_div(total_length, (count - 1)) if count > 1 else total_length
                min_val = center_x - spacing * (count // 2)
        else:
            min_val = min_x + start
            if spacing_mode == "Absolute Spacing":
                spacing = primary
                count = int(math.floor(safe_div((max_x - min_val), spacing))) + 1 if spacing > 0 else 0
            else:
                count = division_count if division_count > 1 else 1
                spacing = safe_div((max_x - min_val), (count - 1)) if count > 1 else (max_x - min_x)
        for i in range(count):
            local_x = min_val + i * spacing
            start_local = FreeCAD.Vector(local_x, min_y - extension, 0)
            end_local = FreeCAD.Vector(local_x, max_y + extension, 0)
            if abs(rotation_deg) > 1e-9:
                center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
                rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
                start_local = rot_local.multVec(start_local - center_local) + center_local
                end_local = rot_local.multVec(end_local - center_local) + center_local
            global_start = localPl.multVec(start_local)
            global_end = localPl.multVec(end_local)
            line = Part.makeLine(global_start, global_end)
            lines.extend(clip_line_to_face(line, face))
        return lines

    # (Other build methods remain unchanged.)
    def buildVerticalPattern(self, obj, face, localPl, pattern_list, patternRepeat=1):
        # [Implementation unchanged]
        T_inv = localPl.inverse()
        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        extension = 2 * math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        alignment = obj.AlignmentMode
        spacing_mode = obj.SpacingMode
        start = float(obj.StartOffset)
        primary = float(obj.PrimarySpacing)
        division_count = obj.Divisions
        rotation_deg = float(obj.RotationAngle)
        lines = []
        if pattern_list:
            current_y = min_y + start
            maxLen = max_y
            seq_index = 0
            while current_y <= maxLen + 1e-9:
                start_local = FreeCAD.Vector(min_x - extension, current_y, 0)
                end_local = FreeCAD.Vector(max_x + extension, current_y, 0)
                if abs(rotation_deg) > 1e-9:
                    center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
                    rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
                    start_local = rot_local.multVec(start_local - center_local) + center_local
                    end_local = rot_local.multVec(end_local - center_local) + center_local
                global_start = localPl.multVec(start_local)
                global_end = localPl.multVec(end_local)
                line = Part.makeLine(global_start, global_end)
                lines.extend(clip_line_to_face(line, face))
                step = pattern_list[seq_index % len(pattern_list)]
                seq_index += 1
                if seq_index >= len(pattern_list):
                    patternRepeat -= 1
                    if patternRepeat <= 0:
                        break
                current_y += step
            return lines
        def safe_div(a, b):
            return a / b if abs(b) > 1e-6 else 0
        if alignment == "Center-outward":
            total_length = max_y - min_y
            center_y = (min_y + max_y) / 2
            if spacing_mode == "Absolute Spacing":
                n_val = int(safe_div(total_length/2, primary)) if primary else 0
                count = 2 * n_val + 1
                spacing = primary
                min_val = center_y - n_val * spacing
            else:
                count = division_count if division_count > 1 else 1
                spacing = safe_div(total_length, (count - 1)) if count > 1 else total_length
                min_val = center_y - spacing*(count//2)
        else:
            min_val = min_y + start
            if spacing_mode == "Absolute Spacing":
                spacing = primary
                count = int(math.floor(safe_div((max_y - min_val), spacing))) + 1 if spacing > 0 else 0
            else:
                count = division_count if division_count > 1 else 1
                spacing = safe_div((max_y - min_val), (count -1)) if count > 1 else (max_y - min_y)
        for i in range(count):
            local_y = min_val + i * spacing
            start_local = FreeCAD.Vector(min_x - extension, local_y, 0)
            end_local = FreeCAD.Vector(max_x + extension, local_y, 0)
            if abs(rotation_deg) > 1e-9:
                center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
                rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
                start_local = rot_local.multVec(start_local - center_local) + center_local
                end_local = rot_local.multVec(end_local - center_local) + center_local
            global_start = localPl.multVec(start_local)
            global_end = localPl.multVec(end_local)
            line = Part.makeLine(global_start, global_end)
            lines.extend(clip_line_to_face(line, face))
        return lines

    def buildCrosshatch(self, obj, face, localPl, pattern_list, patternRepeat=1):
        lines = []
        T_inv = localPl.inverse()
        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        extension = 2 * math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)

        spacing_mode = obj.SpacingMode
        rotation_deg = float(obj.RotationAngle)
        alignment = obj.AlignmentMode
        start = float(obj.StartOffset)
        division_count = obj.Divisions

        # If linked spacing is enabled, use PrimarySpacing for both horizontal and vertical
        if obj.LinkedSpacing:
            hspace = float(obj.PrimarySpacing)
            vspace = float(obj.PrimarySpacing)
        else:
            hspace = float(obj.HorizontalSpacing)
            vspace = float(obj.VerticalSpacing)

        def safe_div(a, b):
            return a / b if abs(b) > 1e-6 else 0

        # --- VERTICAL LINES ---
        if pattern_list:
            # If pattern sequence is used (ABAB...), loop with pattern spacing
            current_x = min_x + start
            seq_index_vert = 0
            repeat_vert = patternRepeat  # local repeat counter for vertical pattern
            while current_x <= max_x + 1e-9 and repeat_vert > 0:
                start_local = FreeCAD.Vector(current_x, min_y - extension, 0)
                end_local = FreeCAD.Vector(current_x, max_y + extension, 0)
                if abs(rotation_deg) > 1e-9:
                    center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                    rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                    start_local = rot_local.multVec(start_local - center_local) + center_local
                    end_local = rot_local.multVec(end_local - center_local) + center_local
                global_start = localPl.multVec(start_local)
                global_end = localPl.multVec(end_local)
                line = Part.makeLine(global_start, global_end)
                lines.extend(clip_line_to_face(line, face))

                step = pattern_list[seq_index_vert % len(pattern_list)]
                seq_index_vert += 1
                if seq_index_vert % len(pattern_list) == 0:
                    repeat_vert -= 1
                    if repeat_vert <= 0:
                        break
                current_x += step
        else:
            # If NO pattern list, check spacing mode
            if spacing_mode == "Absolute Spacing":
                spacing = hspace
                if alignment == "Center-outward":
                    total_length = max_x - min_x
                    center_x = (min_x + max_x) / 2
                    n_val = int(safe_div(total_length / 2, spacing)) if spacing > 0 else 0
                    count = 2 * n_val + 1
                    min_val = center_x - n_val * spacing
                else:
                    min_val = min_x + start
                    if spacing > 0:
                        count = int(math.floor(safe_div((max_x - min_val), spacing))) + 1
                    else:
                        count = 0

                for i in range(count):
                    local_x = min_val + i * spacing
                    start_local = FreeCAD.Vector(local_x, min_y - extension, 0)
                    end_local = FreeCAD.Vector(local_x, max_y + extension, 0)
                    if abs(rotation_deg) > 1e-9:
                        center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                        rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                        start_local = rot_local.multVec(start_local - center_local) + center_local
                        end_local = rot_local.multVec(end_local - center_local) + center_local
                    line = Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local))
                    lines.extend(clip_line_to_face(line, face))

            else:
                # *** FIXED "Quantity Divisions" LOGIC FOR VERTICAL LINES ***
                if alignment == "Center-outward":
                    total_length = max_x - min_x
                    center_x = (min_x + max_x) / 2
                    count = division_count if division_count > 1 else 1
                    spacing = safe_div(total_length, (count - 1)) if count > 1 else total_length
                    min_val = center_x - spacing * (count // 2)
                else:
                    min_val = min_x + start
                    count = division_count if division_count > 1 else 1
                    spacing = safe_div((max_x - min_val), (count - 1)) if count > 1 else (max_x - min_x)

                for i in range(count):
                    local_x = min_val + i * spacing
                    start_local = FreeCAD.Vector(local_x, min_y - extension, 0)
                    end_local = FreeCAD.Vector(local_x, max_y + extension, 0)
                    if abs(rotation_deg) > 1e-9:
                        center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                        rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                        start_local = rot_local.multVec(start_local - center_local) + center_local
                        end_local = rot_local.multVec(end_local - center_local) + center_local
                    global_start = localPl.multVec(start_local)
                    global_end = localPl.multVec(end_local)
                    line = Part.makeLine(global_start, global_end)
                    lines.extend(clip_line_to_face(line, face))

        # --- HORIZONTAL LINES ---
        new_lines = []
        if pattern_list:
            # If pattern sequence is used (ABAB...) for horizontal lines
            current_y = min_y + start
            seq_index_horiz = 0
            repeat_horiz = patternRepeat
            while current_y <= max_y + 1e-9 and repeat_horiz > 0:
                start_local = FreeCAD.Vector(min_x - extension, current_y, 0)
                end_local = FreeCAD.Vector(max_x + extension, current_y, 0)
                if abs(rotation_deg) > 1e-9:
                    center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                    rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                    start_local = rot_local.multVec(start_local - center_local) + center_local
                    end_local = rot_local.multVec(end_local - center_local) + center_local
                global_start = localPl.multVec(start_local)
                global_end = localPl.multVec(end_local)
                line = Part.makeLine(global_start, global_end)
                new_lines.extend(clip_line_to_face(line, face))

                step = pattern_list[seq_index_horiz % len(pattern_list)]
                seq_index_horiz += 1
                if seq_index_horiz % len(pattern_list) == 0:
                    repeat_horiz -= 1
                    if repeat_horiz <= 0:
                        break
                current_y += step
        else:
            if spacing_mode == "Absolute Spacing":
                spacing = vspace
                if alignment == "Center-outward":
                    total_length = max_y - min_y
                    center_y = (min_y + max_y) / 2
                    n_val = int(safe_div(total_length / 2, spacing)) if spacing > 0 else 0
                    count = 2 * n_val + 1
                    min_val = center_y - n_val * spacing
                else:
                    min_val = min_y + start
                    if spacing > 0:
                        count = int(math.floor(safe_div((max_y - min_val), spacing))) + 1
                    else:
                        count = 0

                for i in range(count):
                    local_y = min_val + i * spacing
                    start_local = FreeCAD.Vector(min_x - extension, local_y, 0)
                    end_local = FreeCAD.Vector(max_x + extension, local_y, 0)
                    if abs(rotation_deg) > 1e-9:
                        center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                        rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                        start_local = rot_local.multVec(start_local - center_local) + center_local
                        end_local = rot_local.multVec(end_local - center_local) + center_local
                    new_lines.extend(clip_line_to_face(
                        Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local)), face)
                    )
            else:
                # "Quantity Divisions" logic for horizontal lines
                if alignment == "Center-outward":
                    total_length = max_y - min_y
                    center_y = (min_y + max_y) / 2
                    count = division_count if division_count > 1 else 1
                    spacing = safe_div(total_length, (count - 1)) if count > 1 else total_length
                    min_val = center_y - spacing * (count // 2)
                else:
                    min_val = min_y + start
                    count = division_count if division_count > 1 else 1
                    spacing = safe_div((max_y - min_val), (count - 1)) if count > 1 else (max_y - min_y)

                for i in range(count):
                    local_y = min_val + i * spacing
                    start_local = FreeCAD.Vector(min_x - extension, local_y, 0)
                    end_local = FreeCAD.Vector(max_x + extension, local_y, 0)
                    if abs(rotation_deg) > 1e-9:
                        center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
                        rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
                        start_local = rot_local.multVec(start_local - center_local) + center_local
                        end_local = rot_local.multVec(end_local - center_local) + center_local
                    new_lines.extend(clip_line_to_face(
                        Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local)), face)
                    )

        # Combine new horizontal lines into the main list
        lines.extend(new_lines)

        # If there's a final rotation to apply, transform the lines again
        if abs(rotation_deg) > 1e-9:
            center_local = FreeCAD.Vector((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
            rot_local = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), rotation_deg)
            rotated_list = []
            for edge in lines:
                p1_local = localPl.inverse().multVec(edge.Vertexes[0].Point)
                p2_local = localPl.inverse().multVec(edge.Vertexes[1].Point)
                p1_rot = rot_local.multVec(p1_local - center_local) + center_local
                p2_rot = rot_local.multVec(p2_local - center_local) + center_local
                rotated_line = Part.makeLine(localPl.multVec(p1_rot), localPl.multVec(p2_rot))
                rotated_list.extend(clip_line_to_face(rotated_line, face))
            return rotated_list

        # Otherwise, just return the lines we collected
        return lines


    def buildDiagonalPattern(self, obj, face, localPl, pattern_list, patternRepeat=1):
        lines = []
        T_inv = localPl.inverse()
        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        diagonal = math.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        extension = 2 * diagonal
        diag_angle_rad = math.radians(obj.DiagonalAngle)
        line_dir = FreeCAD.Vector(math.cos(diag_angle_rad), math.sin(diag_angle_rad), 0)
        normal = FreeCAD.Vector(-math.sin(diag_angle_rad), math.cos(diag_angle_rad), 0)
        projections = [ (pt.x*normal.x + pt.y*normal.y) for pt in pts ]
        min_proj = min(projections)
        max_proj = max(projections)
        spacing_mode = obj.SpacingMode
        primary = float(obj.PrimarySpacing)
        divisions = obj.Divisions
        start = float(obj.StartOffset)
        rotation_deg = float(obj.RotationAngle)
        center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
        center_proj_local = center_local.x*normal.x + center_local.y*normal.y
        def safe_div(a,b):
            return a/b if abs(b)>1e-6 else 0
        if pattern_list:
            d = min_proj + start
            seq_index = 0
            pattern_count = patternRepeat
            while d <= max_proj + 1e-9:
                p = center_local + normal * (d - center_proj_local)
                start_local = p - line_dir * extension
                end_local = p + line_dir * extension
                line = Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local))
                lines.extend(clip_line_to_face(line, face))
                step = pattern_list[seq_index % len(pattern_list)]
                seq_index += 1
                if seq_index>=len(pattern_list):
                    pattern_count -= 1
                    if pattern_count<=0:
                        break
                d += step
        else:
            if spacing_mode == "Absolute Spacing":
                if primary <= 1e-9:
                    FreeCAD.Console.PrintError("Spacing is zero in diagonal mode.\n")
                    return lines
                total_len = (max_proj - min_proj)
                dstart = min_proj + start
                count = int(math.floor(safe_div((max_proj - dstart), primary))) + 1
                spacing = primary
            else:
                count = divisions if divisions>1 else 1
                total_len = (max_proj - min_proj)
                spacing = safe_div(total_len, (count-1)) if count>1 else total_len
                dstart = min_proj+start
                if spacing <=1e-9:
                    return lines
            for i in range(count):
                d = dstart + i*spacing
                p = center_local + normal*(d - center_proj_local)
                start_local = p - line_dir * extension
                end_local = p + line_dir * extension
                line = Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local))
                lines.extend(clip_line_to_face(line, face))
        if obj.UseAlternateAngle:
            alt_angle_rad = math.radians(obj.AlternateAngle)
            line_dir_alt = FreeCAD.Vector(math.cos(alt_angle_rad), math.sin(alt_angle_rad), 0)
            normal_alt = FreeCAD.Vector(-math.sin(alt_angle_rad), math.cos(alt_angle_rad), 0)
            proj_alt = [ (pt.x*normal_alt.x + pt.y*normal_alt.y) for pt in pts ]
            min_proj_alt = min(proj_alt)
            max_proj_alt = max(proj_alt)
            if pattern_list:
                d = min_proj_alt + start
                seq_index = 0
                pattern_count = patternRepeat
                while d <= max_proj_alt + 1e-9:
                    p = center_local + normal_alt*(d - (center_local.x*normal_alt.x + center_local.y*normal_alt.y))
                    start_local = p - line_dir_alt*extension
                    end_local = p + line_dir_alt*extension
                    line = Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local))
                    lines.extend(clip_line_to_face(line, face))
                    step = pattern_list[seq_index % len(pattern_list)]
                    seq_index += 1
                    if seq_index>=len(pattern_list):
                        pattern_count -= 1
                        if pattern_count<=0:
                            break
                    d += step
            else:
                if spacing_mode=="Absolute Spacing":
                    sp = primary
                    if sp<=1e-9:
                        return lines
                    total_len = (max_proj_alt - min_proj_alt)
                    dstart_alt = min_proj_alt+start
                    count_alt = int(math.floor(total_len/sp))+1
                else:
                    count_alt = divisions if divisions>1 else 1
                    total_len = (max_proj_alt - min_proj_alt)
                    sp = safe_div(total_len, (count_alt-1)) if count_alt>1 else total_len
                    dstart_alt = min_proj_alt+start
                for i in range(count_alt):
                    d = dstart_alt + i*sp
                    p = center_local + normal_alt*(d - (center_local.x*normal_alt.x + center_local.y*normal_alt.y))
                    start_local = p - line_dir_alt*extension
                    end_local = p + line_dir_alt*extension
                    line = Part.makeLine(localPl.multVec(start_local), localPl.multVec(end_local))
                    lines.extend(clip_line_to_face(line, face))
        if abs(rotation_deg)>1e-9 and lines:
            new_lines = []
            center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
            rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
            for edge in lines:
                p1_local = localPl.inverse().multVec(edge.Vertexes[0].Point)
                p2_local = localPl.inverse().multVec(edge.Vertexes[1].Point)
                p1_rot = rot_local.multVec(p1_local - center_local) + center_local
                p2_rot = rot_local.multVec(p2_local - center_local) + center_local
                rotated_line = Part.makeLine(localPl.multVec(p1_rot), localPl.multVec(p2_rot))
                new_lines.extend(clip_line_to_face(rotated_line, face))
            return new_lines
        return lines

    def buildStaggeredPattern(self, obj, face, localPl):
        lines = []
        T_inv = localPl.inverse()
        pts = [T_inv.multVec(v.Point) for v in face.Vertexes]
        min_x = min(pt.x for pt in pts)
        max_x = max(pt.x for pt in pts)
        min_y = min(pt.y for pt in pts)
        max_y = max(pt.y for pt in pts)
        spacing_mode = obj.SpacingMode
        primary = float(obj.PrimarySpacing)
        divisions = obj.Divisions
        direction = obj.StaggerDirection
        stagger_offset = float(obj.StaggerOffset)
        rotation_deg = float(obj.RotationAngle)
        def safe_div(a, b):
            return a/b if abs(b)>1e-6 else 0
        if spacing_mode=="Absolute Spacing":
            cell_size = primary
        else:
            box_w = max_x - min_x
            box_h = max_y - min_y
            min_side = min(box_w, box_h)
            divs = divisions if divisions>0 else 1
            cell_size = safe_div(min_side, divs)
        if abs(cell_size)<1e-9:
            FreeCAD.Console.PrintError("Cell size is zero in staggered mode.\n")
            return lines
        cols = int(math.floor((max_x - min_x)/cell_size))+1
        rows = int(math.floor((max_y - min_y)/cell_size))+1
        for i in range(rows):
            for j in range(cols):
                cell_min_x = min_x + j*cell_size
                cell_min_y = min_y + i*cell_size
                if direction=="Horizontal" and (i%2==1):
                    cell_min_x += stagger_offset
                elif direction=="Vertical" and (j%2==1):
                    cell_min_y += stagger_offset
                cell_pts = [FreeCAD.Vector(cell_min_x, cell_min_y, 0),
                            FreeCAD.Vector(cell_min_x+cell_size, cell_min_y, 0),
                            FreeCAD.Vector(cell_min_x+cell_size, cell_min_y+cell_size, 0),
                            FreeCAD.Vector(cell_min_x, cell_min_y+cell_size, 0),
                            FreeCAD.Vector(cell_min_x, cell_min_y, 0)]
                cell_wire = Part.makePolygon([localPl.multVec(p) for p in cell_pts])
                lines.extend(clip_line_to_face(cell_wire, face))
        if abs(rotation_deg)>1e-9 and lines:
            center_local = FreeCAD.Vector((min_x+max_x)/2, (min_y+max_y)/2, 0)
            rot_local = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), rotation_deg)
            new_lines = []
            for edge in lines:
                p1_local = localPl.inverse().multVec(edge.Vertexes[0].Point)
                p2_local = localPl.inverse().multVec(edge.Vertexes[1].Point)
                p1_rot = rot_local.multVec(p1_local - center_local)+center_local
                p2_rot = rot_local.multVec(p2_local - center_local)+center_local
                rotated_line = Part.makeLine(localPl.multVec(p1_rot), localPl.multVec(p2_rot))
                new_lines.extend(clip_line_to_face(rotated_line, face))
            return new_lines
        return lines

##########################################################
# User Interface Dialog (PySide2)
##########################################################
class SubdivisionDialog(QtWidgets.QDialog):
    def __init__(self, base_faces, parent=None):
        super(SubdivisionDialog, self).__init__(parent)
        self.setWindowTitle("Parametric Face Subdivider")
        self.base_faces = base_faces  # List of (object, face_name)
        self.preview_obj = None
        self.preview_feature = None  # Persistent preview feature (Part::FeaturePython)
        self.previous_unit = "mm"
        self.featureToEdit = None
        self.initUI()
        self.setupConnections()
        self.updateModeOptions()

    def initUI(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        face_count = len(self.base_faces)
        info_label = QtWidgets.QLabel("Selected Faces: {}".format(face_count))
        main_layout.addWidget(info_label)

        # --- Subdivision Mode Options ---
        subdiv_options_group = QtWidgets.QGroupBox("Subdivision Options")
        subdiv_options_layout = QtWidgets.QHBoxLayout()
        subdiv_mode_label = QtWidgets.QLabel("Subdivision Mode:")
        self.subdivision_mode_combo = QtWidgets.QComboBox()
        self.subdivision_mode_combo.addItems(["Horizontal", "Vertical", "Crosshatch", "Diagonal/Herringbone", "Staggered/Offset Grid"])
        subdiv_options_layout.addWidget(subdiv_mode_label)
        subdiv_options_layout.addWidget(self.subdivision_mode_combo)
        subdiv_options_group.setLayout(subdiv_options_layout)
        main_layout.addWidget(subdiv_options_group)

        # --- Alignment Options ---
        alignment_group = QtWidgets.QGroupBox("Alignment Options")
        alignment_layout = QtWidgets.QHBoxLayout()
        alignment_mode_label = QtWidgets.QLabel("Alignment Mode:")
        self.alignment_mode_combo = QtWidgets.QComboBox()
        self.alignment_mode_combo.addItems(["Edge-to-Edge", "Center-outward"])
        alignment_layout.addWidget(alignment_mode_label)
        alignment_layout.addWidget(self.alignment_mode_combo)
        self.offset_label = QtWidgets.QLabel("Start Offset:")
        self.offset_field = CustomDoubleSpinBox()
        self.offset_field.setRange(-10000, 10000)
        self.offset_field.setValue(0.0)
        self.offset_field.setSuffix(" mm")
        alignment_layout.addWidget(self.offset_label)
        alignment_layout.addWidget(self.offset_field)
        alignment_group.setLayout(alignment_layout)
        main_layout.addWidget(alignment_group)

        # --- Create a New Group: Spacing Mode ---
        spacing_mode_group = QtWidgets.QGroupBox("Spacing Mode")
        spacing_mode_group.setCheckable(True)
        spacing_mode_group.setChecked(True)
        spacing_mode_layout = QtWidgets.QVBoxLayout()

        # Spacing Control (Primary Spacing / Divisions)
        spacing_group = QtWidgets.QGroupBox("Spacing Control")
        spacing_layout = QtWidgets.QHBoxLayout()
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["mm", "inches"])
        spacing_layout.addWidget(QtWidgets.QLabel("Unit:"))
        spacing_layout.addWidget(self.unit_combo)
        self.spacing_mode_combo = QtWidgets.QComboBox()
        self.spacing_mode_combo.addItems(["Absolute Spacing", "Quantity Divisions"])
        spacing_layout.addWidget(self.spacing_mode_combo)
        self.primary_spacing_label = QtWidgets.QLabel("Primary Spacing:")
        self.spacing_stack = QtWidgets.QStackedWidget()
        self.primary_spacing_field = CustomDoubleSpinBox()
        self.primary_spacing_field.setRange(0.001, 10000)
        self.primary_spacing_field.setValue(500.0)
        self.primary_spacing_field.setSuffix(" mm")
        self.divisions_spin = QtWidgets.QSpinBox()
        self.divisions_spin.setRange(1, 1000)
        self.divisions_spin.setValue(10)
        self.spacing_stack.addWidget(self.primary_spacing_field)
        self.spacing_stack.addWidget(self.divisions_spin)
        spacing_layout.addWidget(self.primary_spacing_label)
        spacing_layout.addWidget(self.spacing_stack)
        spacing_group.setLayout(spacing_layout)

        # Pattern Sequence Activation Checkbox and Field
        pattern_group = QtWidgets.QGroupBox("Alternating Pattern (ABAB)")
        pattern_layout = QtWidgets.QVBoxLayout()
        self.pattern_activate_check = QtWidgets.QCheckBox("Use Pattern Sequence")
        pattern_layout.addWidget(self.pattern_activate_check)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Pattern Sequence (comma-separated):"))
        self.pattern_edit = QtWidgets.QLineEdit()
        row.addWidget(self.pattern_edit)
        row.addWidget(QtWidgets.QLabel("Repeat:"))
        self.pattern_repeat_spin = QtWidgets.QSpinBox()
        self.pattern_repeat_spin.setRange(1, 1000)
        self.pattern_repeat_spin.setValue(1)
        row.addWidget(self.pattern_repeat_spin)
        pattern_layout.addLayout(row)
        # Add a note about units (it will reflect the current unit)
        self.pattern_note_label = QtWidgets.QLabel("Values are in mm (or in inches if selected). Example: 50,25,30")
        self.pattern_note_label.setStyleSheet("color: gray; font-style: italic;")
        pattern_layout.addWidget(self.pattern_note_label)
        pattern_group.setLayout(pattern_layout)

        # Add the spacing and pattern groups into the Spacing Mode group
        spacing_mode_layout.addWidget(spacing_group)
        spacing_mode_layout.addWidget(pattern_group)
        spacing_mode_group.setLayout(spacing_mode_layout)
        main_layout.addWidget(spacing_mode_group)

        # --- Crosshatch Spacing ---
        cross_group = QtWidgets.QGroupBox("Crosshatch Spacing")
        cross_layout = QtWidgets.QFormLayout()
        self.hSpacingField = CustomDoubleSpinBox()
        self.hSpacingField.setRange(0.001, 10000)
        self.hSpacingField.setValue(50.0)
        self.hSpacingField.setSuffix(" mm")
        self.vSpacingField = CustomDoubleSpinBox()
        self.vSpacingField.setRange(0.001, 10000)
        self.vSpacingField.setValue(50.0)
        self.vSpacingField.setSuffix(" mm")
        self.linkedSpacingCheck = QtWidgets.QCheckBox("Linked Spacing")
        self.linkedSpacingCheck.setChecked(True)
        self.linkedSpacingCheck.setToolTip("Sync Horizontal/Vertical spacing. Disable for custom grids.")
        cross_layout.addRow("Horizontal Spacing:", self.hSpacingField)
        cross_layout.addRow("Vertical Spacing:", self.vSpacingField)
        cross_layout.addRow(self.linkedSpacingCheck)
        cross_group.setLayout(cross_layout)
        main_layout.addWidget(cross_group)

        # --- Rotation Options ---
        rotation_group = QtWidgets.QGroupBox("Rotation")
        rotation_layout = QtWidgets.QHBoxLayout()
        self.rotation_label = QtWidgets.QLabel("Angle (°):")
        self.rotation_field = QtWidgets.QDoubleSpinBox()
        self.rotation_field.setRange(0, 360)
        self.rotation_field.setValue(0)
        rotation_layout.addWidget(self.rotation_label)
        rotation_layout.addWidget(self.rotation_field)

        # --- Add flip checkboxes ---
        self.flip_h_check = QtWidgets.QCheckBox("Flip H")
        self.flip_v_check = QtWidgets.QCheckBox("Flip V")
        rotation_layout.addWidget(self.flip_h_check)
        rotation_layout.addWidget(self.flip_v_check)

        self.referenceLineBtn = QtWidgets.QPushButton("Pick Reference Line (Edge)")
        rotation_layout.addWidget(self.referenceLineBtn)
        rotation_group.setLayout(rotation_layout)
        main_layout.addWidget(rotation_group)

        # --- Diagonal/Herringbone Options ---
        self.diagonal_options_group = QtWidgets.QGroupBox("Diagonal/Herringbone Options")
        diag_layout = QtWidgets.QHBoxLayout()
        self.diagonal_angle_label = QtWidgets.QLabel("Diagonal Angle:")
        self.diagonal_angle_field = QtWidgets.QDoubleSpinBox()
        self.diagonal_angle_field.setRange(0, 360)
        self.diagonal_angle_field.setValue(45.0)
        self.diagonal_angle_field.setSuffix(" °")
        diag_layout.addWidget(self.diagonal_angle_label)
        diag_layout.addWidget(self.diagonal_angle_field)
        self.alternate_angle_check = QtWidgets.QCheckBox("Alternate Angle")
        diag_layout.addWidget(self.alternate_angle_check)
        self.alternate_angle_field = QtWidgets.QDoubleSpinBox()
        self.alternate_angle_field.setRange(-360, 360)
        self.alternate_angle_field.setValue(-45.0)
        self.alternate_angle_field.setSuffix(" °")
        diag_layout.addWidget(self.alternate_angle_field)
        self.diagonal_options_group.setLayout(diag_layout)
        main_layout.addWidget(self.diagonal_options_group)

        # --- Staggered/Offset Grid Options ---
        self.staggered_options_group = QtWidgets.QGroupBox("Staggered/Offset Grid Options")
        stagger_layout = QtWidgets.QHBoxLayout()
        self.stagger_offset_label = QtWidgets.QLabel("Stagger Offset:")
        self.stagger_offset_field = CustomDoubleSpinBox()
        self.stagger_offset_field.setRange(-10000, 10000)
        self.stagger_offset_field.setValue(2.0)
        self.stagger_offset_field.setSuffix(" mm")
        stagger_layout.addWidget(self.stagger_offset_label)
        stagger_layout.addWidget(self.stagger_offset_field)
        self.stagger_direction_label = QtWidgets.QLabel("Stagger Direction:")
        self.stagger_direction_combo = QtWidgets.QComboBox()
        self.stagger_direction_combo.addItems(["Horizontal", "Vertical"])
        stagger_layout.addWidget(self.stagger_direction_label)
        stagger_layout.addWidget(self.stagger_direction_combo)
        self.staggered_options_group.setLayout(stagger_layout)
        main_layout.addWidget(self.staggered_options_group)

        # --- Clip Offset ---
        clip_group = QtWidgets.QGroupBox("Clip Offset")
        clip_layout = QtWidgets.QHBoxLayout()
        self.clip_offset_check = QtWidgets.QCheckBox("Enable Clip Offset")
        self.clip_offset_field = CustomDoubleSpinBox()
        self.clip_offset_field.setRange(0.0, 10000)
        clip_layout.addWidget(self.clip_offset_check)
        clip_layout.addWidget(QtWidgets.QLabel("Offset:"))
        clip_layout.addWidget(self.clip_offset_field)
        clip_group.setLayout(clip_layout)
        main_layout.addWidget(clip_group)

        self.fuse_check = QtWidgets.QCheckBox("Fuse Subdivisions")
        main_layout.addWidget(self.fuse_check)

        # --- Buttons ---
        button_layout = QtWidgets.QHBoxLayout()
        self.preview_button = QtWidgets.QPushButton("Preview")
        self.generate_button = QtWidgets.QPushButton("Generate")
        self.cancel_button = QtWidgets.QPushButton("Close")
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)



    def setupConnections(self):
        self.spacing_mode_combo.currentTextChanged.connect(self.toggleSpacingMode)
        self.primary_spacing_field.valueChanged.connect(self.updatePreview)
        self.divisions_spin.valueChanged.connect(self.updatePreview)
        self.rotation_field.valueChanged.connect(self.updatePreview)
        self.offset_field.valueChanged.connect(self.updatePreview)
        self.unit_combo.currentIndexChanged.connect(self.onUnitChanged)
        self.referenceLineBtn.clicked.connect(self.pickReferenceLine)
        self.diagonal_angle_field.valueChanged.connect(self.updatePreview)
        self.alternate_angle_check.stateChanged.connect(self.updatePreview)
        self.alternate_angle_field.valueChanged.connect(self.updatePreview)
        self.stagger_offset_field.valueChanged.connect(self.updatePreview)
        self.stagger_direction_combo.currentIndexChanged.connect(self.updatePreview)
        self.clip_offset_check.stateChanged.connect(self.updatePreview)
        self.clip_offset_field.valueChanged.connect(self.updatePreview)
        self.hSpacingField.valueChanged.connect(self.updatePreview)
        self.vSpacingField.valueChanged.connect(self.updatePreview)
        self.linkedSpacingCheck.stateChanged.connect(self.updatePreview)
        # self.pattern_edit.editingFinished.connect(self.updatePreview)
        self.pattern_edit.textChanged.connect(self.updatePreview)
        self.pattern_repeat_spin.valueChanged.connect(self.updatePreview)
        self.flip_h_check.stateChanged.connect(self.updatePreview) 
        self.flip_v_check.stateChanged.connect(self.updatePreview)  
        self.preview_button.clicked.connect(self.updatePreview)
        self.generate_button.clicked.connect(self.generateGeometry)
        self.cancel_button.clicked.connect(self.reject)
        self.alignment_mode_combo.currentTextChanged.connect(self.updatePreview)
        self.subdivision_mode_combo.currentTextChanged.connect(self.updateModeOptions)
        self.fuse_check.stateChanged.connect(self.updatePreview)

    def toggleSpacingMode(self, mode):
        if mode == "Absolute Spacing":
            self.spacing_stack.setCurrentIndex(0)
            self.primary_spacing_label.setText("Spacing:")
        else:
            self.spacing_stack.setCurrentIndex(1)
            self.primary_spacing_label.setText("Divisions:")
        self.updatePreview()

    def updateModeOptions(self):
        mode = self.subdivision_mode_combo.currentText()
        self.diagonal_options_group.setVisible(mode == "Diagonal/Herringbone")
        self.staggered_options_group.setVisible(mode == "Staggered/Offset Grid")
        if mode in ["Horizontal", "Vertical", "Crosshatch", "Diagonal/Herringbone"]:
            self.rotation_field.setEnabled(True)
        else:
            self.rotation_field.setEnabled(False)
        if mode == "Diagonal/Herringbone":  
            self.alignment_mode_combo.setEnabled(False)  
            self.offset_field.setEnabled(False)  
        else:  
            self.alignment_mode_combo.setEnabled(True)  
            self.offset_field.setEnabled(True)  
        self.updatePreview()

    def pickReferenceLine(self):
        FreeCAD.Console.PrintMessage("Please select an edge in the 3D view, then confirm.\n")
        # Placeholder

    def onUnitChanged(self):
        new_unit = self.unit_combo.currentText()
        old_unit = self.previous_unit
        val = self.primary_spacing_field.value()
        if old_unit == "mm" and new_unit == "inches":
            val /= 25.4
        elif old_unit == "inches" and new_unit == "mm":
            val *= 25.4
        self.primary_spacing_field.blockSignals(True)
        self.primary_spacing_field.setValue(val)
        self.primary_spacing_field.blockSignals(False)

        offset_val = self.offset_field.value()
        if old_unit == "mm" and new_unit == "inches":
            offset_val /= 25.4
        elif old_unit == "inches" and new_unit == "mm":
            offset_val *= 25.4
        self.offset_field.blockSignals(True)
        self.offset_field.setValue(offset_val)
        self.offset_field.blockSignals(False)

        clip_val = self.clip_offset_field.value()
        if old_unit == "mm" and new_unit == "inches":
            clip_val /= 25.4
        elif old_unit == "inches" and new_unit == "mm":
            clip_val *= 25.4
        self.clip_offset_field.blockSignals(True)
        self.clip_offset_field.setValue(clip_val)
        self.clip_offset_field.blockSignals(False)

        hVal = self.hSpacingField.value()
        vVal = self.vSpacingField.value()
        if old_unit == "mm" and new_unit == "inches":
            hVal /= 25.4
            vVal /= 25.4
        elif old_unit == "inches" and new_unit == "mm":
            hVal *= 25.4
            vVal *= 25.4
        self.hSpacingField.blockSignals(True)
        self.vSpacingField.blockSignals(True)
        self.hSpacingField.setValue(hVal)
        self.vSpacingField.setValue(vVal)
        self.hSpacingField.blockSignals(False)
        self.vSpacingField.blockSignals(False)

        stVal = self.stagger_offset_field.value()
        if old_unit == "mm" and new_unit == "inches":
            stVal /= 25.4
        elif old_unit == "inches" and new_unit == "mm":
            stVal *= 25.4
        self.stagger_offset_field.blockSignals(True)
        self.stagger_offset_field.setValue(stVal)
        self.stagger_offset_field.blockSignals(False)

        # --- PATTERN SEQUENCE CONVERSION ---
        pattern_text = self.pattern_edit.text().strip()
        if pattern_text:
            try:
                current_values = [float(x.strip()) for x in pattern_text.split(",") if x.strip()]
                if old_unit == "mm" and new_unit == "inches":
                    # Convert mm to inches
                    converted_values = [v / 25.4 for v in current_values]
                elif old_unit == "inches" and new_unit == "mm":
                    # Convert inches to mm
                    converted_values = [v * 25.4 for v in current_values]
                else:
                    converted_values = current_values  # Same unit, no change
                # Update the text field with formatted values
                self.pattern_edit.blockSignals(True)
                self.pattern_edit.setText(", ".join(f"{x:.3f}" for x in converted_values))
                self.pattern_edit.blockSignals(False)
            except Exception as e:
                FreeCAD.Console.PrintWarning(f"Pattern sequence conversion failed: {str(e)}\n")
                pass  # Leave existing text if invalid

        # Update suffixes and unit state
        if new_unit == "inches":
            self.primary_spacing_field.setSuffix(" in")
            self.offset_field.setSuffix(" in")
            self.clip_offset_field.setSuffix(" in")
            self.hSpacingField.setSuffix(" in")
            self.vSpacingField.setSuffix(" in")
            self.stagger_offset_field.setSuffix(" in")
            self.pattern_note_label.setText("Values are in inches. Example: 2.5,1.25,1.0")
        else:
            self.primary_spacing_field.setSuffix(" mm")
            self.offset_field.setSuffix(" mm")
            self.clip_offset_field.setSuffix(" mm")
            self.hSpacingField.setSuffix(" mm")
            self.vSpacingField.setSuffix(" mm")
            self.stagger_offset_field.setSuffix(" mm")
            self.pattern_note_label.setText("Values are in mm. Example: 50,25,30")

        self.previous_unit = new_unit
        self.updatePreview()

    def updatePreview(self):
        doc = FreeCAD.ActiveDocument
        if doc is None or not self.base_faces:
            return

        # ===== NEW CODE: Create a temporary Subdivision object for preview calculation =====
        temp_fp = doc.addObject("Part::FeaturePython", "tempSubdivision")
        SubdivisionPattern(temp_fp)
        ViewProviderSubdivisionPattern(temp_fp.ViewObject)
        temp_fp.BaseFace = (self.base_faces[0][0], [self.base_faces[0][1]])
        # =====================================================================================

        # Now, set properties on the temporary object (replace preview_fp with temp_fp)
        temp_fp.SpacingMode = self.spacing_mode_combo.currentText()

        # Absolute vs. Quantity Divisions
        if self.spacing_stack.currentIndex() == 0:
            # Absolute spacing
            sp_value = self.primary_spacing_field.value()
            if self.unit_combo.currentText() == "inches":
                sp_value *= 25.4
            temp_fp.PrimarySpacing = sp_value
        else:
            # Quantity Divisions
            temp_fp.PrimarySpacing = 0.0

        temp_fp.Divisions = self.divisions_spin.value()

        # Start offset
        off_val = self.offset_field.value()
        if self.unit_combo.currentText() == "inches":
            off_val *= 25.4
        temp_fp.StartOffset = off_val

        # Rotation, Subdivision Mode, Alignment
        temp_fp.RotationAngle   = self.rotation_field.value()
        temp_fp.SubdivisionMode = self.subdivision_mode_combo.currentText()
        temp_fp.AlignmentMode   = self.alignment_mode_combo.currentText()

        # Crosshatch or linked spacing
        hVal = self.hSpacingField.value()
        vVal = self.vSpacingField.value()
        if self.unit_combo.currentText() == "inches":
            hVal *= 25.4
            vVal *= 25.4
        temp_fp.HorizontalSpacing = hVal
        temp_fp.VerticalSpacing   = vVal
        temp_fp.LinkedSpacing     = self.linkedSpacingCheck.isChecked()

        # Clip offset
        temp_fp.UseClipOffset = self.clip_offset_check.isChecked()
        clip_val = self.clip_offset_field.value()
        if self.unit_combo.currentText() == "inches":
            clip_val *= 25.4
        temp_fp.ClipOffset = clip_val

        # Diagonal/Herringbone
        temp_fp.DiagonalAngle     = self.diagonal_angle_field.value()
        temp_fp.UseAlternateAngle = self.alternate_angle_check.isChecked()
        temp_fp.AlternateAngle    = self.alternate_angle_field.value()

        # Staggered grid
        stVal = self.stagger_offset_field.value()
        if self.unit_combo.currentText() == "inches":
            stVal *= 25.4
        temp_fp.StaggerOffset     = stVal
        temp_fp.StaggerDirection  = self.stagger_direction_combo.currentText()

        # UsePatternSequence synchronization
        temp_fp.UsePatternSequence = self.pattern_activate_check.isChecked()

        # Pattern sequence (only if Use Pattern is checked)
        converted_pattern = ""
        if self.pattern_activate_check.isChecked():
            pattern_text = self.pattern_edit.text().strip()
            if pattern_text:
                try:
                    raw_list = [float(x.strip()) for x in pattern_text.split(",") if x.strip()]
                    if self.unit_combo.currentText() == "inches":
                        raw_list = [v * 25.4 for v in raw_list]
                    converted_pattern = ",".join(str(v) for v in raw_list)
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Pattern sequence conversion failed: {e}\n")
        temp_fp.PatternSequence = converted_pattern
        temp_fp.PatternRepeat   = self.pattern_repeat_spin.value()

        # Flip states
        temp_fp.FlipHorizontal = self.flip_h_check.isChecked()
        temp_fp.FlipVertical   = self.flip_v_check.isChecked()

        # Fuse subdivisions if checked
        temp_fp.Fuse = self.fuse_check.isChecked()

        # Force a recompute so that temp_fp.Shape is updated
        doc.recompute()

        # ===== NEW CODE: Extract shape and remove temporary object =====
        temp_shape = temp_fp.Shape.copy()
        doc.removeObject(temp_fp.Name)
        # ====================================================================

        # Create (or update) the preview object (a Part::Feature) to show the preview shape
        if self.preview_obj is None:
            self.preview_obj = doc.addObject("Part::Feature", "SubdivisionPreview")
        self.preview_obj.Shape = temp_shape
        self.preview_obj.ViewObject.LineColor = (1.0, 0.0, 0.0)
        doc.recompute()

        # Toggle UI fields based on pattern usage
        use_pattern = self.pattern_activate_check.isChecked()
        self.primary_spacing_field.setEnabled(not use_pattern)
        self.divisions_spin.setEnabled(not use_pattern)

        # Linked spacing feedback
        if self.linkedSpacingCheck.isChecked():
            self.hSpacingField.setEnabled(False)
            self.vSpacingField.setEnabled(False)
            self.hSpacingField.setToolTip("Horizontal and Vertical spacing are synced.")
            self.vSpacingField.setToolTip("Horizontal and Vertical spacing are synced.")
        else:
            self.hSpacingField.setEnabled(True)
            self.vSpacingField.setEnabled(True)
            self.hSpacingField.setToolTip("")
            self.vSpacingField.setToolTip("")

        doc.recompute()



    def generateGeometry(self):
        doc = FreeCAD.ActiveDocument
        if doc is None:
            return

        if self.featureToEdit:
            fp = self.featureToEdit
        else:
            obj, face_name = self.base_faces[0]
            fp = doc.addObject("Part::FeaturePython", "Subdivision")
            SubdivisionPattern(fp)
            ViewProviderSubdivisionPattern(fp.ViewObject)
            fp.BaseFace = (obj, [face_name])
            try:
                fp.ViewObject.hideProperty("BaseFace")
            except:
                pass

        # SpacingMode
        fp.SpacingMode = self.spacing_mode_combo.currentText()

        # Spacing vs. Divisions
        if self.spacing_stack.currentIndex() == 0:
            # Absolute Spacing
            sp = self.primary_spacing_field.value()
            if self.unit_combo.currentText() == "inches":
                sp *= 25.4
            fp.PrimarySpacing = sp
        else:
            # Quantity Divisions
            fp.PrimarySpacing = 0.0
        fp.Divisions = self.divisions_spin.value()

        # Start offset
        off_val = self.offset_field.value()
        if self.unit_combo.currentText() == "inches":
            off_val *= 25.4
        fp.StartOffset = off_val

        # Rotation, Subdivision Mode, Alignment
        fp.RotationAngle = self.rotation_field.value()
        fp.RotationAxis = FreeCAD.Vector(0, 0, 1)
        fp.SubdivisionMode = self.subdivision_mode_combo.currentText()
        fp.AlignmentMode = self.alignment_mode_combo.currentText()

        # Clip offset
        fp.UseClipOffset = self.clip_offset_check.isChecked()
        cval = self.clip_offset_field.value()
        if self.unit_combo.currentText() == "inches":
            cval *= 25.4
        fp.ClipOffset = cval

        # Crosshatch/Linked
        hVal = self.hSpacingField.value()
        vVal = self.vSpacingField.value()
        if self.unit_combo.currentText() == "inches":
            hVal *= 25.4
            vVal *= 25.4
        fp.HorizontalSpacing = hVal
        fp.VerticalSpacing   = vVal
        fp.LinkedSpacing     = self.linkedSpacingCheck.isChecked()

        # Diagonal/Herringbone
        fp.DiagonalAngle     = self.diagonal_angle_field.value()
        fp.UseAlternateAngle = self.alternate_angle_check.isChecked()
        fp.AlternateAngle    = self.alternate_angle_field.value()

        # Staggered/Offset Grid
        stVal = self.stagger_offset_field.value()
        if self.unit_combo.currentText() == "inches":
            stVal *= 25.4
        fp.StaggerOffset     = stVal
        fp.StaggerDirection  = self.stagger_direction_combo.currentText()

        # --------------------------------------------------------
        # UsePatternSequence synchronization: MISSING LINE ADDED
        # --------------------------------------------------------
        fp.UsePatternSequence = self.pattern_activate_check.isChecked()

        # Pattern sequence (only if "Use Pattern Sequence" is checked)
        converted_pattern = ""
        if self.pattern_activate_check.isChecked():
            pattern_text = self.pattern_edit.text().strip()
            if pattern_text:
                try:
                    raw_list = [float(x.strip()) for x in pattern_text.split(",") if x.strip()]
                    if self.unit_combo.currentText() == "inches":
                        raw_list = [v * 25.4 for v in raw_list]
                    converted_pattern = ",".join(str(v) for v in raw_list)
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Pattern sequence conversion failed: {e}\n")

        fp.PatternSequence = converted_pattern
        fp.PatternRepeat   = self.pattern_repeat_spin.value()

        # Flip states
        fp.FlipHorizontal = self.flip_h_check.isChecked()
        fp.FlipVertical   = self.flip_v_check.isChecked()

        fp.Fuse = self.fuse_check.isChecked()

        # Recompute
        doc.recompute()

        # Confirmation
        result = QtWidgets.QMessageBox.question(
            self,
            "Generation Successful",
            "Subdivision generated successfully.\nGenerate again?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Close
        )
        if result == QtWidgets.QMessageBox.Close:
            self.accept()




    def closeEvent(self, event):
        doc = FreeCAD.ActiveDocument
        if self.preview_obj and self.preview_obj in doc.Objects:
            try:
                doc.removeObject(self.preview_obj.Name)
            except:
                pass
            self.preview_obj = None
        if self.preview_feature and self.preview_feature in doc.Objects:
            try:
                doc.removeObject(self.preview_feature.Name)
            except:
                pass
            self.preview_feature = None
        event.accept()

def main():
    sel = FreeCADGui.Selection.getSelectionEx()
    if not sel:
        FreeCAD.Console.PrintError("Please select one or more faces before running the macro.\n")
        return
    base_faces = []
    for s in sel:
        for i, sub in enumerate(s.SubObjects):
            if hasattr(sub, "Surface"):
                base_faces.append((s.Object, s.SubElementNames[i]))
    if not base_faces:
        FreeCAD.Console.PrintError("No valid faces selected.\n")
        return
    dlg = SubdivisionDialog(base_faces)
    dlg.exec_()

if __name__ == "__main__":
    main()

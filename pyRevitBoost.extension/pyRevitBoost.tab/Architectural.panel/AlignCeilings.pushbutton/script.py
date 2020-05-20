# pylint: disable=import-error
# NOTE: Uses hacky work-around to create alignment with hatch line
# 1. Create reference plane to represent each hatch line
#   1.1. Build stable references to hatch lines
#   1.2. Create dimension using stable references
#   1.3. Extract information about hatch line from dimension
#   1.4. Delete dimension
#   1.5. Create reference plane to represent hatch line
# 2. Align each reference plane with its respective hatch line
# 3. Align reference planes with edges of fixtures
#   3.1 Find edges in ceiling
#   3.2 Align with parallel edge
# https://forums.autodesk.com/t5/revit-api-forum/use-of-align-function-programatically-to-change-the-alignment-of/td-p/6008184
import sys
from System.Collections.Generic import List

from Autodesk.Revit.DB import (BuiltInCategory, ElementId,
                               ElementTransformUtils, FamilyInstance,
                               FilteredElementCollector, HostObjectUtils,
                               Line, Options, Reference, ReferenceArray,
                               RevitLinkInstance, SetComparisonResult, XYZ)
from Autodesk.Revit.Exceptions import InvalidOperationException

from pyrevit import forms
import rpw

from boostutils import is_almost_evenly_divisible, is_parallel, to_XY

__doc__ = '''Align ceilings with fixtures'''
__title__ = 'Align\nCeilings'
__author__ = 'Zachary Mathews'

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
view = uidoc.ActiveView
options = Options()
options.View = view


# NOTE: In order to align ceiling grids in Revit, we have to create a reference
# plane aligned to each hatch line and then align it with a fixture. This
# method deletes those reference planes so we don't litter our models. It also
# allows the command to be run more than once without complaint about breaking
# our previous alignments.
def cleanup(grid):
    reference_planes = [line['reference_plane'].Id for line in grid]
    doc.Delete(List[ElementId](reference_planes))


selected = uidoc.Selection.GetElementIds()
if not selected:
    forms.alert(
        msg='You must first select ceilings.',
        title='Error'
    )
    sys.exit()

ceilings = FilteredElementCollector(doc, selected) \
    .OfCategory(BuiltInCategory.OST_Ceilings) \
    .ToElements()
if not ceilings:
    forms.alert(
        msg='You must first select ceilings.',
        title='Error'
    )
    sys.exit()

links = FilteredElementCollector(doc) \
    .OfCategory(BuiltInCategory.OST_RvtLinks) \
    .OfClass(RevitLinkInstance) \
    .ToElements()
docs = [link.GetLinkDocument() for link in links] + [doc]
selected_doc = forms.SelectFromList.show(
    context=sorted([d.Title for d in docs]),
    title='Select model',
    width=400,
    height=400,
    multiselect=False
)
[fixtures_doc] = [d for d in docs if d.Title == selected_doc]

categories = fixtures_doc.Settings.Categories
selected_category = forms.SelectFromList.show(
    context=sorted([category.Name for category in categories]),
    title='Select category',
    width=400,
    height=600,
    multiselect=False
)
[category] = [c for c in categories if c.Name == selected_category]

fixtures = FilteredElementCollector(fixtures_doc) \
    .OfCategoryId(category.Id) \
    .OfClass(FamilyInstance) \
    .ToElements()
if not fixtures:
    forms.alert(
        msg='The selected model does not contain fixtures of that category.',
        title='Error'
    )
    sys.exit()

cnt = 0
max = len(ceilings)
failed = []
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.TransactionGroup('Align ceilings with light fixtures'):
        # 1. Create reference plane to represent hatch line
        ceiling_grids = []
        with rpw.db.Transaction('Create ref planes to represent hatch lines'):
            for ceiling in ceilings:
                [ceiling_down_face] = HostObjectUtils.GetBottomFaces(ceiling)
                face = \
                    ceiling.GetGeometryObjectFromReference(ceiling_down_face)

                stable_ref = \
                    ceiling_down_face.ConvertToStableRepresentation(doc)
                try:
                    material = doc.GetElement(face.MaterialElementId)
                    pattern = doc \
                        .GetElement(material.SurfacePatternId) \
                        .GetFillPattern()
                except (AttributeError, InvalidOperationException):
                    failed.append(ceiling)
                    cnt += 1
                    pb.update_progress(cnt, max)
                    continue

                grid = []
                for i in range(pattern.GridCount):
                    # 1.1. Build stable references to hatch lines
                    hatch_line_refs = ReferenceArray()
                    for j in range(2):
                        hatch_line_index = (i+1) + (j*pattern.GridCount*2)
                        hatch_line_stable_ref = '{0}/{1}'.format(
                            stable_ref,
                            hatch_line_index
                        )

                        hatch_line_ref = \
                            Reference.ParseFromStableRepresentation(
                                doc,
                                hatch_line_stable_ref
                            )
                        hatch_line_refs.Append(hatch_line_ref)

                    # 1.2. Create dimension using stable references
                    dimension = doc.Create.NewDimension(
                        view,
                        Line.CreateBound(XYZ.Zero, XYZ(10, 0, 0)),
                        hatch_line_refs
                    )
                    ElementTransformUtils.MoveElement(
                        doc,
                        dimension.Id,
                        XYZ(1e-9, 0, 0)
                    )

                    # 1.3. Extract information about hatch line from dimension
                    hatch_line = dimension.References[0]
                    origin = \
                        dimension.Origin \
                        - dimension.Curve.Direction * (dimension.Value / 2.0)
                    spacing = dimension.Value
                    direction = dimension.Curve.Direction \
                        .CrossProduct(face.FaceNormal) \
                        .Normalize()

                    # 1.4. Delete dimension
                    doc.Delete(dimension.Id)

                    # 1.5. Create reference plane to represent hatch line
                    reference_plane = doc.Create.NewReferencePlane(
                        origin,
                        origin + direction * 2.00000,
                        face.FaceNormal,
                        view
                    )
                    grid.append({
                        'direction': direction,
                        'spacing': spacing,
                        'hatch_line': hatch_line,
                        'reference_plane': reference_plane
                    })

                # Get cross-axis spacing
                grid[0]['cross_axis_spacing'] = grid[1]['spacing']
                grid[1]['cross_axis_spacing'] = grid[0]['spacing']

                ceiling_grids.append((ceiling, grid))

        # 2. Align each reference plane with its respective hatch line
        # NOTE: Reference planes must be committed before alignment
        with rpw.db.Transaction('Align reference planes with hatch lines'):
            for ceiling, grid in ceiling_grids:
                for line in grid:
                    hatch_line = line['hatch_line']
                    rp = line['reference_plane']
                    reference_plane_stable_ref = '{0}:0:SURFACE'.format(
                        Reference(rp).ConvertToStableRepresentation(doc)
                    )
                    reference_plane_ref = \
                        Reference.ParseFromStableRepresentation(
                            doc,
                            reference_plane_stable_ref
                        )

                    doc.Create.NewAlignment(
                        view,
                        reference_plane_ref,
                        hatch_line
                    )

        # 3. Align reference planes with edges of fixtures
        with rpw.db.Transaction('Align reference planes with edges'):
            for ceiling, grid in ceiling_grids:
                # 3.1 Find edges in ceiling
                [ceiling_down_face_ref] = \
                    HostObjectUtils.GetBottomFaces(ceiling)
                ceiling_down_face = \
                    ceiling.GetGeometryObjectFromReference(
                        ceiling_down_face_ref
                    )

                edges = []
                for fixture in fixtures:
                    up = Line.CreateBound(
                        fixture.Location.Point,
                        fixture.Location.Point + XYZ(0, 0, 1)
                    )
                    up_intersects = ceiling_down_face.Intersect(up)

                    down = Line.CreateBound(
                        fixture.Location.Point,
                        fixture.Location.Point - XYZ(0, 0, 1)
                    )
                    down_intersects = ceiling_down_face.Intersect(down)

                    does_intersect = (
                        up_intersects == SetComparisonResult.Overlap
                        or down_intersects == SetComparisonResult.Overlap
                    )
                    if does_intersect:
                        [geom_inst] = fixture.get_Geometry(options)
                        fixture_edges = [
                            o for o in geom_inst.GetInstanceGeometry()
                            if type(o) == Line
                        ]
                        edges.extend(fixture_edges)

                if not edges:
                    cleanup(grid)
                    failed.append(ceiling)
                    cnt += 1
                    pb.update_progress(cnt, max)
                    continue

                # 3.2 Align with parallel edge
                for line in grid:
                    for edge in edges:
                        if (
                            is_almost_evenly_divisible(
                                edge.Length,
                                line['cross_axis_spacing']
                            )
                            and
                            is_parallel(
                                edge.Direction,
                                line['direction']
                            )
                        ):
                            vector = \
                                to_XY(edge.Origin) \
                                - line['reference_plane'].BubbleEnd
                            translation = \
                                vector.DotProduct(
                                    line['reference_plane'].Normal
                                ) * line['reference_plane'].Normal

                            ElementTransformUtils.MoveElement(
                                doc,
                                line['reference_plane'].Id,
                                translation
                            )

                            break
                    else:
                        failed.append(ceiling)
                        break

                cleanup(grid)
                cnt += 1
                pb.update_progress(cnt, max)


if failed:
    uidoc.Selection.SetElementIds(List[ElementId]([e.Id for e in failed]))
    forms.alert(
        title='Error',
        msg='Align Ceilings failed for {} ceiling{}.\n{} left selected.'
            .format(
                len(failed),
                's' if len(failed) > 1 else '',
                'They were' if len(failed) > 1 else 'It was'
            )
    )

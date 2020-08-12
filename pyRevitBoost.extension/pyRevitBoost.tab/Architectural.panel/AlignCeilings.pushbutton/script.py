# pylint: disable=import-error
# NOTE: Uses hacky work-around to create alignment with hatch line
# https://forums.autodesk.com/t5/revit-api-forum/use-of-align-function-programatically-to-change-the-alignment-of/td-p/6008184
from pyrevit import forms

__doc__ = '''Align ceilings with fixtures.'''
__title__ = 'Align\nCeilings'
__author__ = 'Zachary Mathews'
__context__ = 'Ceilings'


class CategoryOption(forms.TemplateListItem):
    @property
    def name(self):
        return self.item.Name

    def __lt__(self, other):
        return self.item.Name < other.item.Name


class DocumentOption(forms.TemplateListItem):
    @property
    def name(self):
        return self.item.Title

    def __lt__(self, other):
        return self.item.Title < other.item.Title


def align_ceiling_representation_with_gridlines(ceiling, grid, view, doc):
    from Autodesk.Revit.DB import Reference

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


def align_grid_with_edges(grid, edges, doc):
    from Autodesk.Revit.DB import ElementTransformUtils
    from boostutils import to_XY

    def _find_edges_in_direction(edges, direction):
        for edge in edges:
            if _is_parallel(edge.Direction, direction):
                yield edge

    def _find_fitting_edges(edges, spacing):
        for edge in edges:
            if _is_almost_evenly_divisible(edge.Length, spacing):
                yield edge

    def _is_parallel(v1, v2):
        return (
            v1.Normalize().IsAlmostEqualTo(v2)
            or v1.Normalize().Negate().IsAlmostEqualTo(v2)
        )

    def _is_almost_evenly_divisible(numerator, denominator):
        is_divisible = abs(numerator-denominator) < 1e-9
        while (
            not is_divisible
            and numerator > denominator
        ):
            numerator /= denominator
            is_divisible = abs(numerator-denominator) < 1e-9

        return is_divisible

    succeeded, failed = [], []
    for line in grid:
        parallel_edges = _find_edges_in_direction(
            edges=edges,
            direction=line['direction']
        )
        fitting_edges = _find_fitting_edges(
            edges=parallel_edges,
            spacing=line['cross_axis_spacing']
        )

        edge = next(fitting_edges, None)
        if edge:
            vector = to_XY(edge.Origin) - line['reference_plane'].BubbleEnd
            translation = \
                vector.DotProduct(
                    line['reference_plane'].Normal
                ) * line['reference_plane'].Normal

            ElementTransformUtils.MoveElement(
                doc,
                line['reference_plane'].Id,
                translation
            )

            succeeded.append(line)

        else:
            failed.append(line)

    return (succeeded, failed)


def find_hosted_fixtures(ceiling, fixtures):
    from Autodesk.Revit.DB import (HostObjectUtils, Line, SetComparisonResult,
                                   XYZ)

    [ceiling_down_face_ref] = \
        HostObjectUtils.GetBottomFaces(ceiling)
    ceiling_down_face = \
        ceiling.GetGeometryObjectFromReference(
            ceiling_down_face_ref
        )

    hosted_fixtures = []
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
            hosted_fixtures.append(fixture)

    return hosted_fixtures


def get_ceiling_representation(ceilings, view, doc):
    from Autodesk.Revit.DB import (ElementTransformUtils, HostObjectUtils,
                                   Line, Reference, ReferenceArray, XYZ)
    from Autodesk.Revit.Exceptions import InvalidOperationException

    ceiling_grids = []
    failed = []
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

    return (ceiling_grids, failed)


def get_fixture_edges(fixture, view):
    from Autodesk.Revit.DB import Line, Options

    options = Options()
    options.View = view
    [geom_inst] = fixture.get_Geometry(options)
    fixture_edges = [
        o for o in geom_inst.GetInstanceGeometry()
        if type(o) == Line
    ]

    return fixture_edges


def get_fixtures_of_category(category, doc):
    import rpw
    return rpw.db.Collector(
        doc=doc,
        of_category=category,
        of_class='FamilyInstance'
    ).get_elements(wrapped=False)


def get_links():
    import rpw
    return rpw.db.Collector(
        of_category='OST_RvtLinks',
        of_class='RevitLinkInstance'
    ).get_elements(wrapped=False)


if __name__ == '__main__':
    import sys
    from System.Collections.Generic import List

    from Autodesk.Revit.DB import ElementId

    import rpw

    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    view = uidoc.ActiveView
    selection = rpw.ui.Selection()

    ceilings = selection.get_elements(wrapped=False)
    if not ceilings:
        forms.alert(
            msg='You must first select ceilings.',
            title='Error'
        )
        sys.exit()

    links = get_links()
    docs = [DocumentOption(doc)]
    for link in links:
        link_doc = link.GetLinkDocument()
        if link_doc:
            docs.append(DocumentOption(link_doc))

    fixtures_doc = forms.SelectFromList.show(
        context=sorted(docs, key=lambda d: d.name),
        title='Select model',
        width=400,
        height=400,
        multiselect=False
    )
    if not fixtures_doc:
        sys.exit()

    categories = [CategoryOption(c) for c in fixtures_doc.Settings.Categories]
    category = forms.SelectFromList.show(
        context=sorted(categories, key=lambda c: c.name),
        title='Select category',
        width=400,
        height=600,
        multiselect=False
    )
    if not category:
        sys.exit()

    fixtures = get_fixtures_of_category(
        category=category.Name,
        doc=fixtures_doc
    )
    if not fixtures:
        forms.alert(
            msg='The selected model does not contain fixtures of '
                'that category.',
            title='Error'
        )
        sys.exit()

    cnt = 0
    max = len(ceilings)
    failed = []
    with forms.ProgressBar(title='{value} of {max_value}') as pb:
        with rpw.db.TransactionGroup('Align ceilings with light fixtures'):

            with rpw.db.Transaction('Create representation of ceiling grids'):
                ceiling_grids, failed = get_ceiling_representation(
                    ceilings=ceilings,
                    view=view,
                    doc=doc
                )

                failed.extend(failed)
                cnt += len(failed)
                pb.update_progress(cnt, max)

            with rpw.db.Transaction('Align representation with gridlines'):
                for ceiling, grid in ceiling_grids:
                    align_ceiling_representation_with_gridlines(
                        ceiling=ceiling,
                        grid=grid,
                        view=view,
                        doc=doc
                    )

            with rpw.db.Transaction('Align gridlines with edges'):
                for ceiling, grid in ceiling_grids:
                    # Get fixtures under the current ceiling
                    hosted_fixtures = find_hosted_fixtures(
                        ceiling=ceiling,
                        fixtures=fixtures
                    )

                    # Get fixture edges
                    edges_in_ceiling = []
                    for fixture in hosted_fixtures:
                        edges_in_ceiling.extend(
                            get_fixture_edges(fixture, view)
                        )

                    # Align grid with fixture edges
                    succeeded, _failed = align_grid_with_edges(
                        grid=grid,
                        edges=edges_in_ceiling,
                        doc=doc
                    )
                    if _failed:
                        failed.append(ceiling)

                    # Cleanup
                    reference_planes = [
                        gridline['reference_plane'].Id
                        for gridline in grid
                    ]
                    doc.Delete(List[ElementId](reference_planes))

                    # Update progress
                    cnt += 1
                    pb.update_progress(cnt, max)

    if failed:
        selection.clear()
        selection.add(failed)
        selection.update()
        forms.alert(
            title='Error',
            msg='Align Ceilings failed for {} ceiling{}.\n{} left selected.'
                .format(
                    len(failed),
                    's' if len(failed) > 1 else '',
                    'They were' if len(failed) > 1 else 'It was'
                )
        )

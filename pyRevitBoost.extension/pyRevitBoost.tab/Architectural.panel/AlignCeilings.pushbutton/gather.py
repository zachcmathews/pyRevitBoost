from Autodesk.Revit.DB import (BuiltInCategory, ElementTransformUtils, FamilyInstance, FilteredElementCollector, HostObjectUtils, Line,
                               Options, Reference, ReferenceArray, RevitLinkInstance, SetComparisonResult, XYZ)


def find_hosted_fixtures(ceiling, fixtures):
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


def get_ceilings(selected, doc):
    return FilteredElementCollector(doc, selected) \
        .OfCategory(BuiltInCategory.OST_Ceilings) \
        .ToElements()


def get_fixtures_of_category(category, doc):
    return FilteredElementCollector(doc) \
        .OfCategoryId(category.Id) \
        .OfClass(FamilyInstance) \
        .ToElements()


def get_fixture_edges(fixture, view):
    options = Options()
    options.View = view
    [geom_inst] = fixture.get_Geometry(options)
    fixture_edges = [
        o for o in geom_inst.GetInstanceGeometry()
        if type(o) == Line
    ]

    return fixture_edges


def get_ceiling_representation(ceilings, view, doc):
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


def get_links(doc):
    return FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_RvtLinks) \
        .OfClass(RevitLinkInstance) \
        .ToElements()

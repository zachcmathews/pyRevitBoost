# pylint: disable=import-error

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

from Autodesk.Revit.DB import ElementTransformUtils, Reference

from boostutils import is_almost_evenly_divisible, is_parallel, to_XY


def align_ceiling_representation_with_gridlines(ceiling, grid, view, doc):
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
        if is_parallel(edge.Direction, direction):
            yield edge


def _find_fitting_edges(edges, spacing):
    for edge in edges:
        if is_almost_evenly_divisible(edge.Length, spacing):
            yield edge

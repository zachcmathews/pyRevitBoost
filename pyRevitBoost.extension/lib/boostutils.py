# pylint: disable=import-error
import math
import inspect

from Autodesk.Revit.DB import (Domain, Ellipse, Line, XYZ)

from pyrevit.coreutils import yaml
import rpw


class memoize(object):
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        key = self.key(args, kwargs)
        if key not in self.cache:
            self.cache[key] = self.func(*args, **kwargs)
        return self.cache[key]

    def normalize_args(self, args, kwargs):
        spec = inspect.getargs(self.func.__code__).args
        return dict(kwargs.items() + zip(spec, args))

    def key(self, args, kwargs):
        normalized_args = self.normalize_args(args, kwargs)
        return tuple(sorted(normalized_args.items()))


def _convert_yamldotnet_to_python(ynode, level=0):
    if hasattr(ynode, 'Children'):
        d = {}
        value_childs = []
        for child in ynode.Children:
            # Handle child dictionaries
            if hasattr(child, 'Key') and hasattr(child, 'Value'):
                d[child.Key.Value] = \
                    _convert_yamldotnet_to_python(child.Value, level=level+1)
            elif hasattr(child, 'Value'):
                val = child.Value
                value_childs.append(val)

            # Handle child lists
            elif hasattr(child, 'Children'):
                val = _convert_yamldotnet_to_python(child, level=level+1)
                value_childs.append(val)
            elif hasattr(child, 'Values'):
                value_childs.append(child.Values)

        return value_childs or d
    else:
        return ynode.Value


def is_close(a, b, abs_tol=1e-9):
    return abs(a-b) < abs_tol


def is_parallel(v1, v2):
    return v1.Normalize().IsAlmostEqualTo(v2) \
           or v1.Normalize().Negate().IsAlmostEqualTo(v2)


def is_almost_evenly_divisible(numerator, denominator):
    while (numerator > denominator):
        numerator = numerator / denominator

    return is_close(numerator, denominator)


def draw_BoundingBoxXYZ_2D(doc, view, bounding_box):
    x0y0 = XYZ(bounding_box.Min.X, bounding_box.Min.Y, 0)
    x1y1 = XYZ(bounding_box.Max.X, bounding_box.Max.Y, 0)
    x0y1 = XYZ(x0y0.X, x1y1.Y, 0)
    x1y0 = XYZ(x1y1.X, x0y0.Y, 0)

    curves = [
        Line.CreateBound(x0y0, x0y1),
        Line.CreateBound(x0y1, x1y1),
        Line.CreateBound(x1y1, x1y0),
        Line.CreateBound(x1y0, x0y0)
    ]
    for curve in curves:
        doc.Create.NewDetailCurve(view, curve)


# FIXME: Needs to project edges onto XY plane then draw as detail curves
def draw_Solid_2D(doc, view, solid):
    curves = [e.AsCurve() for e in solid.Edges]
    for curve in curves:
        doc.Create.NewDetailCurve(view, curve)


def find_closest(to, elements):
    return min(
        elements,
        key=lambda e:
            e.Location.Point.DistanceTo(
                to.Location.Point
            )
    )


def get_name(el):
    return rpw.db.Element(el).name


def get_parameter(el, name):
    instanceParam = el.LookupParameter(name)
    typeParam = el.Symbol.LookupParameter(name)
    if instanceParam:
        return instanceParam
    elif typeParam:
        return typeParam
    else:
        return None


# # TODO: Test me
# def get_solids(doc, element, view, options):
#     if view and not options:
#         options = Options()
#         options.View = view
#     elif not options:
#         options = Options()

#     # Recursively iterate over GeometryElement chaining
#     # all solids into a list
#     def extract_solids(geometry_element):
#         geometry_elements = [
#             o for o in geometry_element
#             if type(o) == GeometryElement
#         ]
#         solids = list(chain(
#             [o for o in geometry_element if type(o) == Solid],
#             chain(extract_solids(e) for e in geometry_elements)
#         ))
#         return solids

#     geometry_element = element.get_Geometry(options)
#     return extract_solids(geometry_element)


def has_electrical_connectors(element):
    return (
        element.MEPModel
        and element.MEPModel.ConnectorManager
        and not element.MEPModel.ConnectorManager.Connectors.IsEmpty()
    )


def get_electrical_connectors(element, default=[]):
    if has_electrical_connectors(element):
        return [
            c for c in element.MEPModel.ConnectorManager.Connectors
            if c.Domain == Domain.DomainElectrical
        ]
    else:
        return default


def load_as_python(yaml_file):
    return _convert_yamldotnet_to_python(yaml.load(yaml_file))


def to_XY(xyz):
    return XYZ(xyz.X, xyz.Y, 0)


def draw_circle(center, radius, view, doc):
    xaxis, yaxis = XYZ.BasisX, XYZ.BasisY
    start, end = 0, 2*math.pi
    circle = Ellipse.CreateCurve(
        center,
        radius,
        radius,
        xaxis,
        yaxis,
        start,
        end
    )
    doc.Create.NewDetailCurve(
        view,
        circle
    )

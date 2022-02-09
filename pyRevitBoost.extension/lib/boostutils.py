# pylint: disable=import-error
from System.ComponentModel import INotifyPropertyChanged, PropertyChangedEventArgs
import pyevent


class NotifyPropertyChangedBase(INotifyPropertyChanged):
    PropertyChanged = None

    def __init__(self):
        self.PropertyChanged, self._propertyChangedCaller = \
            pyevent.make_event()

    def add_PropertyChanged(self, value):
        self.PropertyChanged += value

    def remove_PropertyChanged(self, value):
        self.PropertyChanged -= value

    def OnPropertyChanged(self, property_name):
        if self.PropertyChanged is not None:
            self._propertyChangedCaller(
                self, PropertyChangedEventArgs(property_name))


class notify_property(property):
    def __init__(self, getter):
        def newgetter(slf):
            try:
                return getter(slf)
            except AttributeError:
                return None
        super(notify_property, self).__init__(newgetter)

    def setter(self, setter):
        def newsetter(slf, value):
            oldvalue = self.fget(slf)
            if oldvalue != value:
                setter(slf, value)
                slf.OnPropertyChanged(setter.__name__)

        return property(
            fget=self.fget,
            fset=newsetter,
            fdel=self.fdel,
            doc=self.__doc__)


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
        import inspect
        spec = inspect.getargs(self.func.__code__).args
        return dict(kwargs.items() + zip(spec, args))

    def key(self, args, kwargs):
        normalized_args = self.normalize_args(args, kwargs)
        return tuple(sorted(normalized_args.items()))


def is_inside_bounding_box(point, box, include_z=True):
    point = box.Transform.Inverse.OfVector(point)
    if include_z:
        return (
            box.Min.X <= point.X <= box.Max.X
            and box.Min.Y <= point.Y <= box.Max.Y
            and box.Min.Z <= point.Z <= box.Max.Z
        )
    else:
        return (
            box.Min.X <= point.X <= box.Max.X
            and box.Min.Y <= point.Y <= box.Max.Y
        )


def is_inside_viewplan(point, view):
    from Autodesk.Revit.DB import ViewPlan
    assert(type(view) is ViewPlan)
    return is_inside_bounding_box(point, view.CropBox, include_z=False)


def draw_BoundingBoxXYZ_2D(doc, view, bounding_box):
    from Autodesk.Revit.DB import Line, XYZ

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


def draw_circle(center, radius, view, doc):
    import math
    from Autodesk.Revit.DB import Ellipse, XYZ

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


def get_name(el):
    import rpw
    return rpw.db.Element(el).name


def get_parameter(el, name=None, builtin=None):
    from Autodesk.Revit.DB import BuiltInParameter

    if builtin:
        param = getattr(BuiltInParameter, builtin)
        instanceParam = el.get_Parameter(param)
        if not instanceParam:
            typeParam = el.Symbol.get_Parameter(param)
    elif name:
        instanceParam = el.LookupParameter(name)
        if not instanceParam:
            typeParam = el.Symbol.LookupParameter(name)
    else:
        return None

    if instanceParam:
        return instanceParam
    elif typeParam:
        return typeParam
    else:
        return None


def load_as_python(yaml_file):
    from pyrevit.coreutils import yaml

    def _convert_yamldotnet_to_python(ynode, level=0):
        if hasattr(ynode, 'Children'):
            d = {}
            value_childs = []
            for child in ynode.Children:
                # Handle child dictionaries
                if hasattr(child, 'Key') and hasattr(child, 'Value'):
                    d[child.Key.Value] = _convert_yamldotnet_to_python(
                        child.Value,
                        level=level+1
                    )
                elif hasattr(child, 'Value'):
                    val = child.Value
                    value_childs.append(val)

                # Handle child lists
                elif hasattr(child, 'Children'):
                    val = _convert_yamldotnet_to_python(
                        child,
                        level=level+1
                    )
                    value_childs.append(val)
                elif hasattr(child, 'Values'):
                    value_childs.append(child.Values)

            return value_childs or d
        else:
            return ynode.Value

    yamldotnet = yaml.load(yaml_file)
    if yamldotnet:
        return _convert_yamldotnet_to_python(yamldotnet)
    else:
        return None


def load_tsv(tsv):
    import codecs

    out = []
    error_codes = [
        '#VALUE!', '#NAME?', '#DIV/0!', '#REF!',
        '#NULL!', '#N/A', '#NUM!'
    ]
    with codecs.open(tsv, 'r', encoding='utf8') as f:
        for line in f.readlines():
            values = line.rstrip('\t\r\n').split('\t')
            if not any(v in error_codes for v in values):
                out.append(values)

    return out


def to_XY(xyz):
    from Autodesk.Revit.DB import XYZ
    return XYZ(xyz.X, xyz.Y, 0)

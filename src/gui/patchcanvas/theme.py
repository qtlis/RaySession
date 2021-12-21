#!/usr/bin/python3
import json
import os
import sys

from PyQt5.QtGui import QColor, QPen, QFont, QBrush
from PyQt5.QtCore import Qt, QTimer

# from gui.patchcanvas import theme_default
from . import canvas

def print_error(string: str):
    sys.stderr.write("patchcanvas.theme::%s\n" % string)

def _to_qcolor(color):
    ''' convert a color given with a string, a list or a tuple (of ints)
    to a QColor.
    returns None if color has a incorrect value.'''
    if isinstance(color, str):
        intensity_ratio = 1.0
        opacity_ratio = 1.0
        
        if color.startswith('-'):
            color = color.partition('-')[2].strip()
            intensity_ratio = - 1.0

        if '*' in color:
            words = color.split('*')
            next_for_opac = False
            
            for i in range(len(words)):
                if i == 0:
                    color = words[i].strip()
                    continue
                
                if not words[i]:
                    next_for_opac = True
                    continue
                
                if next_for_opac:
                    try:
                        opacity_ratio *= float(words[i].strip())
                    except:
                        pass
                
                    next_for_opac = False
                    continue
                
                try:
                    intensity_ratio *= float(words[i].strip())
                except:
                    pass
        
        qcolor = QColor(color)
        if not qcolor.isValid():
            return None

        if intensity_ratio == 1.0 and opacity_ratio == 1.0:
            return qcolor
        
        if intensity_ratio < 0.0:
            qcolor = QColor(
                255 - qcolor.red(), 255 - qcolor.green(),
                255 - qcolor.blue(), qcolor.alpha())
        
        if opacity_ratio != 1.0:
            qcolor.setAlphaF(opacity_ratio * qcolor.alphaF())
        
        return qcolor.lighter(int(100 * intensity_ratio))

    if isinstance(color, (tuple, list)):
        if not 3 <= len(color) <= 4:
            return None

        for col in color:
            if not isinstance(col, int):
                return None
            
            if not 0 <= col <= 255:
                return None
        
        return QColor(*color)
    
    return None


class StyleAttributer:
    def __init__(self, path, parent=None):
        self.subs = []

        self._border_color = None
        self._border_width = None
        self._border_style = None
        self._background_color = None
        self._background2_color = None
        self._text_color = None
        self._font_name = None
        self._font_size = None
        self._font_width = None

        self._path = path
        self._parent = parent
        
        self._fill_pen = None
        self._font = None
    
    def set_attribute(self, attribute: str, value):
        err = False
        
        if attribute == 'border-color':
            self._border_color = _to_qcolor(value)
            if self._border_color is None:
                err = True
                
        elif attribute == 'border-width':
            if isinstance(value, (int, float)):
                self._border_width = float(value)
            else:
                err = True
                
        elif attribute == 'border-style':
            if isinstance(value, str):
                value = value.lower()
                if value in ('solid', 'normal'):
                    self._border_style = Qt.SolidLine
                elif value in ('nopen', 'none'):
                    self._border_style = Qt.NoPen
                elif value == 'dash':
                    self._border_style = Qt.DashLine
                elif value == 'dashdot':
                    self._border_style = Qt.DashDotLine
                elif value == 'dashdotdot':
                    self._border_style = Qt.DashDotDotLine
                else:
                    err = True
            else:
                err = True

        elif attribute == 'background':
            self._background_color = _to_qcolor(value)
            if self._background_color is None:
                err = True
                
        elif attribute == 'background2':
            self._background2_color = _to_qcolor(value)
            if self._background2_color is None:
                err = True
                
        elif attribute == 'text-color':
            self._text_color = _to_qcolor(value)
            if self._text_color is None:
                err = True
                
        elif attribute == 'font-name':
            if isinstance(value, str):
                self._font_name = value
            else:
                err = True
                
        elif attribute == 'font-size':
            if isinstance(value, int):
                self._font_size = value
            else:
                err = True
                
        elif attribute == 'font-width':
            if isinstance(value, int):
                value = min(value, 99)
                value = max(value, 0)
                self._font_width = value
            elif isinstance(value, str):
                value = value.lower()
                if value == 'normal':
                    self._font_state = QFont.Normal
                elif value == 'bold':
                    self._font_state = QFont.Bold
                else:
                    err = True
            else:
                err = True
        else:
            print_error("%s:unknown key: %s" % (self._path, attribute))

        if err:
            print_error("%s:invalid value for %s: %s"
                        % (self._path, attribute, str(value)))
    
    def set_style_dict(self, context: str, style_dict: dict):
        if context:
            begin, point, end = context.partition('.')
            
            if begin not in self.subs:
                print_error("%s:invalid ignored key: %s" % (self._path, begin))
                return
            self.__getattribute__(begin).set_style_dict(end, style_dict)
            return
        
        for key, value in style_dict.items():
            self.set_attribute(key, value)
    
    def get_value_of(self, attribute, orig_path='', needed_attribute=''):
        # returns the value of given attribute for this theme section
        # if this value is not present in this theme section,
        # it will look into parent sections.
        # Note that for 'selected' section, it will look in 'selected' section
        # of parent before looking in parent section.
        if attribute not in self.__dir__():
            print_error("get_value_of, invalide attribute: %s" % attribute)
            return None
        
        if not orig_path:
            orig_path = self._path

        for path_end in ('selected',):
            if (orig_path.endswith('.' + path_end)
                    and path_end in self.subs
                    and self._path + '.' + path_end != orig_path):
                return self.selected.get_value_of(
                    attribute, self._path, needed_attribute)

        if self.__getattribute__(attribute) is None:
            if (needed_attribute
                    and self.__getattribute__(needed_attribute) is not None):
                return None
                
            if self._parent is None:
                print_error("get_value_of: %s None value and no parent"
                            % self._path)
                return None
            return self._parent.get_value_of(
                attribute, orig_path, needed_attribute)

        return self.__getattribute__(attribute)
    
    def fill_pen(self):
        if self._fill_pen is None:
            self._fill_pen = QPen(
                QBrush(self.get_value_of('_border_color')),
                self.get_value_of('_border_width'),
                self.get_value_of('_border_style'))
        
        return self._fill_pen
    
    def background_color(self):
        return self.get_value_of('_background_color')
    
    def background2_color(self):
        return self.get_value_of('_background2_color',
                                 needed_attribute='_background_color')
    
    def text_color(self):
        return self.get_value_of('_text_color')
    
    def font(self):
        font_ = QFont(self.get_value_of('_font_name'))
        font_.setPixelSize(self.get_value_of('_font_size'))
        font_.setWeight(self.get_value_of('_font_width'))
        return font_


class UnselectedStyleAttributer(StyleAttributer):
    def __init__(self, path, parent=None):
        StyleAttributer.__init__(self, path, parent=parent)
        self.selected = StyleAttributer(path + '.selected', self)
        self.subs.append('selected')


class BoxStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.hardware = UnselectedStyleAttributer(path + '.hardware', self)
        self.client = UnselectedStyleAttributer(path + '.client', self)
        self.monitor = UnselectedStyleAttributer(path + '.monitor', self)
        self.subs += ['hardware', 'client', 'monitor']


class PortStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.audio = UnselectedStyleAttributer(path + '.audio', self)
        self.midi = UnselectedStyleAttributer(path + '.midi', self)
        self.cv = UnselectedStyleAttributer(path + '.cv', self)
        self.subs += ['audio', 'midi', 'cv']


class LineStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.audio = UnselectedStyleAttributer(path + '.audio', self)
        self.midi = UnselectedStyleAttributer(path + '.midi', self)
        self.disconnecting = StyleAttributer(path + '.disconnecting', self)
        self.subs += ['audio', 'midi', 'disconnecting']


class GuiButtonStyleAttributer(StyleAttributer):
    def __init__(self, path, parent):
        StyleAttributer.__init__(self, path, parent)
        self.gui_visible = StyleAttributer('.gui_visible', self)
        self.gui_hidden = StyleAttributer('.gui_hidden', self)
        self.subs += ['gui_visible', 'gui_hidden']


class Theme(StyleAttributer):
    def __init__(self):
        StyleAttributer.__init__(self, '')

        # fallbacks values for all (ugly style, but better than nothing)
        self._border_color = QColor('white')
        self._border_width = 1
        self._border_style = Qt.SolidLine
        self._background_color = QColor('black')
        self._background2_color = QColor('black')
        self._text_color = QColor('white')
        self._font_name = "Deja Vu Sans"
        self._font_size = 11
        self._font_width = QFont.Normal # QFont.Normal is 50

        self.background_color = QColor('black')
        self.box_shadow_color = QColor('gray')
        self.monitor_color = QColor(190, 158, 0)
        self.port_height = 16
        self.port_spacing = 2
        self.port_type_spacing = 2
        self.port_offset = 0
        self.port_grouped_width = 19
        self.box_spacing = 4
        self.box_spacing_horizontal = 24
        self.magnet = 12
        self.hardware_rack_width = 5

        self.aliases = {}

        self.box = BoxStyleAttributer('.box', self)
        self.box_wrapper = BoxStyleAttributer('.box_wrapper', self)
        self.box_header_line = BoxStyleAttributer('.box_header_line', self)
        self.box_shadow = BoxStyleAttributer('.box_shadow', self)
        self.portgroup = PortStyleAttributer('.portgroup', self)
        self.port = PortStyleAttributer('.port', self)
        self.line = LineStyleAttributer('.line', self)
        self.rubberband = StyleAttributer('.rubberband', self)
        self.hardware_rack = UnselectedStyleAttributer('.hardware_rack', self)
        self.monitor_decoration = UnselectedStyleAttributer('.monitor_decoration', self)
        self.gui_button = GuiButtonStyleAttributer('.gui_button', self)
        
        self.subs += ['box', 'box_wrapper', 'box_header_line', 'box_shadow',
                      'portgroup', 'port', 'line',
                      'rubberband', 'hardware_rack',
                      'monitor_decoration', 'gui_button']
        
    def read_theme(self, theme_dict: dict):
        if not isinstance(theme_dict, dict):
            print_error("invalid dict read error")
            return
        
        self.aliases.clear()
        
        # first read if there are any aliases
        for key, value in theme_dict.items():
            if key != 'aliases':
                continue
            
            if not isinstance(value, dict):
                print_error("'%s' must contains a dictionnary, ignored" % key)
                continue
            
            for alias_key, alias_value in value.items():
                if not isinstance(alias_key, str):
                    print_error("alias key must be a string. Ignore: %s"
                                % str(alias_key))
                    continue
                
                self.aliases[alias_key] = alias_value
            
            break
        
        # read and parse the dict
        for key, value in theme_dict.items():
            if key == 'aliases':
                continue
            
            begin, point, end = key.partition('.')
            
            if not isinstance(value, dict):
                print_error("'%s' must contains a dictionnary, ignored" % key)
                continue
            
            if key == 'body':
                for body_key, body_value in value.items():
                    if body_key in (
                            'port-height', 'port-spacing', 'port-type-spacing',
                            'box-spacing', 'box-spacing-horizontal', 'magnet',
                            'hardware-rack-width', 'port-offset'):
                        if not isinstance(body_value, int):
                            continue
                        self.__setattr__(body_key.replace('-', '_'), body_value)
                    elif body_key == 'background':
                        self.background_color = _to_qcolor(body_value)
                        if self.background_color is None:
                            self.background_color = QColor('black')
                    elif body_key == 'box-shadow-color':
                        self.box_shadow_color = _to_qcolor(body_value)
                        if self.box_shadow_color is None:
                            self.box_shadow_color = QColor('black')
                    elif body_key == 'monitor-color':
                        self.monitor_color = _to_qcolor(body_value)
                        if self.monitor_color is None:
                            self.monitor_color = QColor(190, 158, 0)
                continue
            
            if begin not in self.subs:
                print_error("invalid ignored key: %s" % key)
                continue

            # replace alias with alias value
            for sub_key, sub_value in value.items():
                if not isinstance(sub_value, str):
                        continue
                
                for alias_key, alias_value in self.aliases.items():
                    if alias_key not in sub_value:
                        continue
                    
                    if sub_value == alias_key:
                        value[sub_key] = alias_value
                        break
                    
                    new_words = []
                    
                    for word in sub_value.split(' '):
                        if word == alias_key:
                            new_words.append(alias_value)
                        else:
                            new_words.append(word)
                    
                    value[sub_key] = ' '.join(new_words)
                    

            sub_attributer = self.__getattribute__(begin)
            sub_attributer.set_style_dict(end, value)
    




if __name__ == '__main__':
    # theme = Theme()
    
    import json
    from theme_default import default_theme
    
    for key, value in default_theme.items():
        for sub_key, sub_value in value.items():
            if isinstance(sub_value, (list, tuple)):
                qcol = _to_qcolor(sub_value)
                # print(sub_value, qcol.name(QColor.HexArgb), qcol.alpha())
                if qcol.alpha() == 255:
                    print(sub_value, qcol.name())
                    default_theme[key][sub_key] = qcol.name()
                else:
                    print(sub_value, qcol.name(QColor.HexArgb))
                    default_theme[key][sub_key] = qcol.name(QColor.HexArgb)
                
    
    with open('/home/houston/.config/RaySession/patchbay_themes/Black Gold/theme.json', 'w+') as f:
            json.dump(default_theme, f, indent=2)
    
    # theme.read_theme(default_theme)
    # print(theme.port.audio.font())

# ---------------------------------------------------------------------------- #
import configparser
import os

# ---------------------------------------------------------------------------- #
from lib_yeoul import err_with_name


# ---------------------------------------------------------------------------- #
class SimpleConfigManager:
    def __init__(self, filename):
        self.filename = filename
        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        self.load_config()

    def load_config(self):
        conf = self.config
        if not os.path.exists(self.filename):
            self.save_config()
        conf.read(self.filename)

    def save_config(self):
        conf = self.config
        with open(self.filename, "w") as configfile:
            conf.write(configfile)

    def get_items(self, section):
        conf = self.config
        if not conf.has_section(section):
            err_with_name(ValueError, f"{section=} does not exist")

        return conf.items(section)

    def get_sections(self):
        return self.config.sections()

    def add_section(self, section: str):
        conf = self.config
        if not conf.has_section(section):
            conf.add_section(section)
            self.save_config()
        else:
            err_with_name(ValueError, f"{section=} already exists")

    def get_option(self, section, option, option_type, fallback_value=None):
        try:
            if option_type == "int":
                value = self.config.get(section, option, fallback=fallback_value)
                if value == "":
                    err_with_name(ValueError, "Empty string cannot be converted to int")
                return int(value)
            elif option_type == "float":
                value = self.config.get(section, option, fallback=fallback_value)
                if value == "":
                    err_with_name(ValueError, "Empty string cannot be converted to float")
                return float(value)
            elif option_type == "bool":
                return self.config.getboolean(section, option, fallback=fallback_value)
            else:
                return self.config.get(section, option, fallback=fallback_value)
        except ValueError as e:
            err_with_name(ValueError, "Invalid value type")

    def get_default_option(self, option, option_type, fallback_value=None):
        return self.get_option(configparser.DEFAULTSECT, option, option_type, fallback_value)

    def set_option(self, section, option, value=None):
        conf = self.config
        if section != configparser.DEFAULTSECT and not conf.has_section(section):
            err_with_name(ValueError, f"{section=} does not exist")
        conf.set(section, option, str(value))
        self.save_config()

    def set_default_option(self, option, value=None):
        return self.set_option(configparser.DEFAULTSECT, option, str(value))

    def remove_section(self, section):
        conf = self.config
        self.load_config()
        if section == configparser.DEFAULTSECT:
            err_with_name(ValueError, f"{section=} cannot be removed")
        if conf.has_section(section):
            conf.remove_section(section)
            self.save_config()

    def remove_option(self, section, option):
        conf = self.config
        self.load_config()
        if not conf.has_section(section) and section != configparser.DEFAULTSECT:
            err_with_name(ValueError, f"{section=} does not exist")
        removed = conf.remove_option(section, option)
        if removed:
            self.save_config()
        else:
            err_with_name(ValueError, f"{option=} not found in section {section=}")

    def remove_default_option(self, option):
        self.remove_option(configparser.DEFAULTSECT, option)


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

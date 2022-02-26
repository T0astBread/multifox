"""
gui contains everything related to interactive graphical user
interfaces of multifox.
"""


from typing import List, Optional

import gi

from . import model


def init_gtk_modules():
    """
    init_gtk_modules initializes GDK and GTK which is required for
    importing them.

    These modules are lazily loaded because they contain some
    initialization logic that can print to stderr. This can be
    irritating when the program is executed to generate shell
    completions.

    Mypy can't handle modules returned from functions so the import
    has to be done separately.
    """
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")


def select_profile(config: model.Configuration) -> Optional[str]:
    """
    select_profile displays a GUI dialog to select a profile and
    returns the selected profile's name.

    `None` is returned if no profile was selected, for example
    because the dialog was cancelled.
    """
    init_gtk_modules()

    # These modules are lazily loaded, so the import is okay.
    from gi.repository import Gdk, Gtk  # pylint: disable=import-outside-toplevel

    window = Gtk.Dialog(use_header_bar=True)
    window.set_default_geometry(600, 800)
    window.set_title("Select profile")
    window.get_header_bar().set_show_close_button(False)
    window.connect("destroy", Gtk.main_quit)

    profile_list_model = Gtk.ListStore(str)

    for profile in config.profiles:
        profile_list_model.append([profile.name])

    profile_list = Gtk.TreeView(model=profile_list_model)
    profile_list.set_activate_on_single_click(True)

    # HACK: Use single-entry arrays for making state mutable through GTK callbacks.
    selected_profile: List[Optional[str]] = [None]

    def get_selected_profile():
        return selected_profile[0]

    def set_selected_profile(profile: str):
        selected_profile[0] = profile

    confirmed: List[bool] = [False]

    def get_confirmed():
        return confirmed[0]

    def set_confirmed(is_confirmed):
        confirmed[0] = is_confirmed

    profile_list.get_selection().connect(
        "changed",
        lambda selection: selection.selected_foreach(
            lambda store, path, iter: set_selected_profile(store.get_value(iter, 0))
        ),
    )

    def confirm_and_close():
        set_confirmed(True)
        window.close()

    def handle_key_event_on_profile_list(_, evt: Gdk.EventKey):
        _, keyval = evt.get_keyval()
        if keyval == Gdk.KEY_Return:
            confirm_and_close()

    profile_list.connect(
        "key-release-event",
        handle_key_event_on_profile_list,
    )

    window.get_content_area().add(profile_list)

    name_renderer = Gtk.CellRendererText()
    name_column = Gtk.TreeViewColumn("Name", name_renderer, text=0)
    profile_list.append_column(name_column)

    cancel_button = Gtk.Button("Cancel")
    cancel_button.connect("clicked", lambda _: window.close())
    window.get_header_bar().pack_start(cancel_button)

    confirm_button = Gtk.Button("Confirm")
    confirm_button.get_style_context().add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
    confirm_button.connect("clicked", lambda _: confirm_and_close())
    window.get_header_bar().pack_end(confirm_button)

    window.show_all()
    Gtk.main()

    return get_selected_profile() if get_confirmed() else None

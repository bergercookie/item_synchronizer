"""Types used across this package."""
from datetime import datetime
from typing import Any, Callable

# Type of the identifier of an item in each side.
ID = str

# Type of an arbitrary item
Item = Any

# Insertion Function - when called with the contents of an item it should return
# the ID of the newly added item
InserterFn = Callable[[Item], ID]
# Update Function - update an item given by the item ID, using the (possibly partial) new
# contents specified by Item
UpdaterFn = Callable[[ID, Item], None]
# Deletion Function - Delete the item given by the specified ID
DeleterFn = Callable[[ID], None]
# Conversion Function - convert an item from the format of one source to the format of another.
ConverterFn = Callable[[Item], Item]

# Date Getter Function - Given an item should return the corresponding date of it.
DateGetterFn = Callable[[Item], datetime]

# ItemGetter Function - Given the ID of an Item of one source return the corresponding item on
# the other source. ItemGetter functions should raise "KeyError" in case the item is not
# present (e.g. was previously deleted)
ItemGetterFn = Callable[[ID], Item]

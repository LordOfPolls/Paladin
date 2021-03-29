import enum


class EventFlags(enum.IntEnum):
    memJoin = 1  # a user joined
    memLeave = 2  # a user left
    memUpdate = 3  # a user's details were updated
    memBan = 4  # a user was banned
    memUnban = 5  # a user was unbanned
    msgDelete = 6  # a message was deleted
    msgEdit = 7  # a message was edited
    chnlPurge = 8  # a channel was purged


class ModActions(enum.IntEnum):
    kick = 1
    ban = 2
    purge = 3
    warn = 4

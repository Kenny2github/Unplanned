from enum import IntEnum, auto as EnumAuto

__all__ = [
    'Button',
    'SockMsg',
    'MiscOpcode',
    'InputMode',
    'BulletType'
]

class Button(IntEnum):
    UP = 1 #up button on keyboard
    DOWN = 2 #down ^
    LEFT = 3 #left ^
    RIGHT = 4 #right ^
    FIRE = 5 #fire button, mouse click or right bumper
    START = 6 #start button, enter or start
    SHIELD = 7 #aim button, right click or left bumper
    ROT = 8 #not a button, used to set player rotation
    FORTH = 9 #not a button, used for joystick analog movement
    PICKUP = 10 #button to pick up items

class MiscOpcode(IntEnum):
    WEAPON_SET = 50 #changed weapon
    BULLET_ADD = 51 #bullet data
    WEAPON_GET = 52 #new weapon in slot

class SockMsg(IntEnum):
    ADD = 0x0 #player joined
    YOU = 127 #sent once at start of connection, used to set player.sprite
    BYE = 128 #unused
    BAC = 200 #set backdrop, received once at start of connection
    DEL = 255 #player left

class InputMode(IntEnum):
    KEYANDMOUSE = EnumAuto()
    CONTROLLER = EnumAuto()

class BulletType(IntEnum):
    LIGHT = 0
    SHELL = 1
    MEDIUM = 2
    HEAVY = 3
    EXPLOSIVE = 4

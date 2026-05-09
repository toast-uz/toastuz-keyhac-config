import platform
import time
import traceback

from keyhac import *


# =====================================================
# NICOLA constants
# =====================================================

# 同時打鍵判定幅（秒）
SIMULT_WINDOW_SEC = 0.18
# 左親指単打（英数キー兼用）の遅延確定幅（秒）
LEFT_ONESHOT_DELAY_SEC = 0.25

# IME モード（環境差があるため内部状態も併用）
IME_MODE_EISU = 0
IME_MODE_KANA = 1

# 物理キー名（OSにより切替）
WIN_MUHENKAN = "Muhenkan"
WIN_HENKAN = "Henkan"
WIN_EISU = "Eisu"
MAC_LEFT_THUMB = "Eisu"
MAC_RIGHT_THUMB = "Kana"
MAC_EISU = "Eisu"
MAC_RIGHT_THUMB_SINGLE_CONVERT_KEY = None
MAC_TOGGLE_KEYS = ["Ctrl-J", "Kana"]

# NICOLA 同時打鍵対象キー
NICOLA_MAIN_KEYS = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Minus",
    "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P",
    "OpenBracket", "CloseBracket",
    "A", "S", "D", "F", "G", "H", "J", "K", "L", "Semicolon",
    "Quote",
    "Z", "X", "C", "V", "B", "N", "M", "Comma", "Period", "Slash", "BackSlash",
]

# NICOLA かな 3面テーブル（無/左/右）
NICOLA_TABLE = {
    # 数字段（NeoCat例準拠）
    "1": ("1", "KEY:Shift-Slash", "KEY:Shift-1"),
    "2": ("2", "KEY:Slash", "KEY:Shift-2"),
    "3": ("3", "KEY:Shift-Plus", "KEY:Shift-3"),
    "4": ("4", "KEY:CloseBracket", "KEY:Shift-4"),
    "5": ("5", "KEY:BackSlash", "KEY:Shift-5"),
    "6": ("6", "KEY:Shift-6", "KEY:Alt-CloseBracket"),
    "7": ("7", "KEY:Shift-7", "KEY:Alt-BackSlash"),
    "8": ("8", "KEY:Shift-8", "KEY:Shift-Comma"),
    "9": ("9", "KEY:Shift-9", "KEY:Shift-Period"),
    "0": ("0", "KEY:Shift-0", "KEY:Shift-CloseBracket"),
    "Minus": ("KEY:Minus", "KEY:Shift-Minus", "KEY:Shift-BackSlash"),
    # 右側記号キー
    "OpenBracket": ("KEY:OpenBracket", "KEY:Shift-OpenBracket", "KEY:OpenBracket"),
    "CloseBracket": ("KEY:CloseBracket", "KEY:Shift-CloseBracket", "KEY:CloseBracket"),
    "Q": ("。", "ぁ", ""), "W": ("か", "え", "が"), "E": ("た", "り", "だ"),
    "R": ("こ", "ゃ", "ご"), "T": ("さ", "れ", "ざ"), "Y": ("ら", "ぱ", "よ"),
    "U": ("ち", "ぢ", "に"), "I": ("く", "ぐ", "る"), "O": ("つ", "づ", "ま"),
    "P": ("、", "ぴ", "ぇ"), "A": ("う", "を", "ゔ"), "S": ("し", "あ", "じ"),
    "D": ("て", "な", "で"), "F": ("け", "ゅ", "げ"), "G": ("せ", "も", "ぜ"),
    "H": ("は", "ば", "み"), "J": ("と", "ど", "お"), "K": ("き", "ぎ", "の"),
    "L": ("い", "ぽ", "ょ"), "Semicolon": ("ん", ";", "っ"), "Z": (".", "ぅ", "ゑ"),
    "Quote": ("KEY:Quote", "KEY:Shift-Quote", "KEY:Quote"),
    "X": ("ひ", "ー", "び"), "C": ("す", "ろ", "ず"), "V": ("ふ", "や", "ぶ"),
    "B": ("へ", "ぃ", "べ"), "N": ("め", "ぷ", "ぬ"), "M": ("そ", "ぞ", "ゆ"),
    "Comma": ("ね", "ぺ", "む"), "Period": ("ほ", "ぼ", "わ"), "Slash": ("・", "゛", "ぉ"),
    "BackSlash": ("KEY:BackSlash", "KEY:Shift-BackSlash", "KEY:BackSlash"),
}

# かな -> ローマ字（IMEローマ字入力向け）
ROMAJI_MAP = {
    "あ": "A", "い": "I", "う": "U", "え": "E", "お": "O",
    "か": "KA", "き": "KI", "く": "KU", "け": "KE", "こ": "KO",
    "さ": "SA", "し": "SI", "す": "SU", "せ": "SE", "そ": "SO",
    "た": "TA", "ち": "TI", "つ": "TU", "て": "TE", "と": "TO",
    "な": "NA", "に": "NI", "ぬ": "NU", "ね": "NE", "の": "NO",
    "は": "HA", "ひ": "HI", "ふ": "HU", "へ": "HE", "ほ": "HO",
    "ま": "MA", "み": "MI", "む": "MU", "め": "ME", "も": "MO",
    "や": "YA", "ゆ": "YU", "よ": "YO",
    "ら": "RA", "り": "RI", "る": "RU", "れ": "RE", "ろ": "RO",
    "わ": "WA", "を": "WO", "ん": "NN",
    "が": "GA", "ぎ": "GI", "ぐ": "GU", "げ": "GE", "ご": "GO",
    "ざ": "ZA", "じ": "ZI", "ず": "ZU", "ぜ": "ZE", "ぞ": "ZO",
    "だ": "DA", "ぢ": "DI", "づ": "DU", "で": "DE", "ど": "DO",
    "ば": "BA", "び": "BI", "ぶ": "BU", "べ": "BE", "ぼ": "BO",
    "ぱ": "PA", "ぴ": "PI", "ぷ": "PU", "ぺ": "PE", "ぽ": "PO",
    "ぁ": "LA", "ぃ": "LI", "ぅ": "LU", "ぇ": "LE", "ぉ": "LO",
    "ゃ": "LYA", "ゅ": "LYU", "ょ": "LYO", "っ": "LTU", "ゔ": "VU",
}

ROMAJI_KEYNAME_MAP = {
    "-": "Minus",
    ",": "Comma",
    ".": "Period",
    "/": "Slash",
    ";": "Semicolon",
}

DIRECT_KEYSEQ_MAP = {}

logger = getLogger("Config")


class NicolaEngine:
    def __init__(self, keymap, keytable, os_name):
        self.keymap = keymap
        self.keytable = keytable
        self.os_name = os_name

        if os_name == "windows":
            self.left_thumb = WIN_MUHENKAN
            self.right_thumb = WIN_HENKAN
            self.eisu_key = WIN_EISU
            self.toggle_key = "Muhenkan"
            self.convert_key = "Henkan"
            self.kana_on_key = "Henkan"
            self.eisu_on_key = "Eisu"
            self.toggle_keys = [self.toggle_key]
        else:
            self.left_thumb = MAC_LEFT_THUMB
            self.right_thumb = MAC_RIGHT_THUMB
            self.eisu_key = MAC_EISU
            self.toggle_key = "Kana"
            self.convert_key = MAC_RIGHT_THUMB_SINGLE_CONVERT_KEY
            self.kana_on_key = "Kana"
            self.eisu_on_key = "Eisu"
            self.toggle_keys = MAC_TOGGLE_KEYS

        self.ime = False
        self.shift_time = [None, None]
        self.shift_down = [False, False]
        self.suppress_oneshot = [False, False]
        self.pending_key = None
        self.pending_key_time = None
        self.left_oneshot_pending = False
        self.left_oneshot_at = None

        self._setup()

    def _send(self, *keys):
        with self.keymap.get_input_context() as input_ctx:
            for k in keys:
                input_ctx.send_key(k)

    def _send_first(self, keys):
        for key in keys:
            try:
                self._send(key)
                return True
            except Exception:
                logger.info(f"NICOLA: send failed key={key}")
        return False

    def _send_romaji(self, kana):
        if kana in DIRECT_KEYSEQ_MAP:
            for key in DIRECT_KEYSEQ_MAP[kana]:
                self._send(key)
            return

        if kana in ("。", "."):
            self._send("Period")
            return
        if kana in ("、", ","):
            self._send("Comma")
            return
        if kana == "・":
            self._send("Slash")
            return
        if kana == "ー":
            self._send("Minus")
            return

        seq = ROMAJI_MAP.get(kana)
        if not seq:
            logger.info(f"NICOLA: romaji map missing for '{kana}'")
            return

        for c in seq:
            self._send(ROMAJI_KEYNAME_MAP.get(c, c.upper()))

    def _set_ime_kana(self):
        self._send(self.kana_on_key)
        self.ime = True

    def _set_ime_eisu(self):
        self._send(self.eisu_on_key)
        self.ime = False

    def _has_marked_text(self):
        # macOSのアクセシビリティ属性から未確定文字の有無を推定
        try:
            elm = self.keymap.focus
            if not elm:
                return False
            names = elm.get_attribute_names()
            if "AXMarkedText" in names:
                marked = elm.get_attribute_value("AXMarkedText")
                return bool(marked)
        except Exception:
            pass
        return False

    def _apply_left_oneshot_if_due(self):
        if not self.left_oneshot_pending:
            return
        if self.left_oneshot_at is None:
            return
        if time.time() - self.left_oneshot_at < LEFT_ONESHOT_DELAY_SEC:
            return

        if not self.ime:
            self._set_ime_kana()
        else:
            self._send_first(self.toggle_keys)

        self.left_oneshot_pending = False
        self.left_oneshot_at = None

    def _emit_key(self, key, side):
        table = NICOLA_TABLE.get(key)
        if not table:
            self._send(key)
            return

        # 英数モードでは、親指同時打鍵なし（平打ち）は通常の英数入力を優先する
        if (not self.ime) and (side is None):
            self._send(key)
            return

        kana = table[0]
        if side == 0:
            kana = table[1]
        elif side == 1:
            kana = table[2]

        if not kana:
            return

        if kana.startswith("KEY:"):
            self._send(kana[4:])
            return

        if not self.ime:
            self._set_ime_kana()
        self._send_romaji(kana)

    def _apply_pending_plain(self):
        if self.pending_key:
            self._emit_key(self.pending_key, None)
            self.pending_key = None
            self.pending_key_time = None

    def _thumb_start(self, idx):
        self._apply_left_oneshot_if_due()
        now = time.time()
        self.shift_down[idx] = True
        self.suppress_oneshot[idx] = False

        # 直前文字が保留中なら同時打鍵として確定
        if self.pending_key and self.pending_key_time and now - self.pending_key_time <= SIMULT_WINDOW_SEC:
            self._emit_key(self.pending_key, idx)
            self.pending_key = None
            self.pending_key_time = None
            self.suppress_oneshot[idx] = True
            self.shift_time[idx] = None
            return

        self.shift_time[idx] = now

    def _thumb_stop(self, idx):
        self._apply_left_oneshot_if_due()
        self.shift_down[idx] = False
        self.shift_time[idx] = None

        if self.suppress_oneshot[idx]:
            return

        # 親指単打
        if idx == 0:
            # 左親指（英数キー兼用）は単打確定を少し遅延させる
            self.left_oneshot_pending = True
            self.left_oneshot_at = time.time()
        else:
            # 英数モード中は変換しない
            if self.ime and self.convert_key:
                self._send(self.convert_key)

    def _eisu_oneshot(self):
        self._apply_left_oneshot_if_due()
        # 英数単独打鍵:
        # - 原則: 英数モードへ
        # - 未確定文字がある場合: ひらがな/カタカナトグル
        if self._has_marked_text():
            self._send_first(self.toggle_keys)
            return
        self._set_ime_eisu()

    def _key_down(self, key):
        def _f():
            self._apply_left_oneshot_if_due()
            self._apply_pending_plain()
            now = time.time()

            # 親指先押し -> 文字後押し の同時打鍵を優先判定
            if self.shift_down[0] and self.shift_time[0] and now - self.shift_time[0] <= SIMULT_WINDOW_SEC:
                self._emit_key(key, 0)
                self.suppress_oneshot[0] = True
                self.left_oneshot_pending = False
                self.left_oneshot_at = None
                logger.info(f"NICOLA: emit left {key} (thumb-first)")
                return
            if self.shift_down[1] and self.shift_time[1] and now - self.shift_time[1] <= SIMULT_WINDOW_SEC:
                self._emit_key(key, 1)
                self.suppress_oneshot[1] = True
                logger.info(f"NICOLA: emit right {key} (thumb-first)")
                return

            self.pending_key = key
            self.pending_key_time = now
            self.suppress_oneshot = [True, True]
            logger.info(f"NICOLA: main down {key}")
        return _f

    def _key_up(self, key):
        def _f():
            self._apply_left_oneshot_if_due()
            if self.pending_key == key:
                # 親指未介入なら平面確定
                self._emit_key(key, None)
                self.pending_key = None
                self.pending_key_time = None
                logger.info(f"NICOLA: emit plain {key}")
        return _f

    def _setup(self):
        logger.info(
            "NICOLA: physical keys "
            f"left={self.left_thumb}, right={self.right_thumb}, eisu={self.eisu_key}"
        )

        self.keytable[f"D-{self.left_thumb}"] = lambda: self._thumb_start(0)
        self.keytable[f"U-{self.left_thumb}"] = lambda: self._thumb_stop(0)
        self.keytable[f"D-{self.right_thumb}"] = lambda: self._thumb_start(1)
        self.keytable[f"U-{self.right_thumb}"] = lambda: self._thumb_stop(1)
        self.keytable[f"O-{self.eisu_key}"] = self._eisu_oneshot

        for key in NICOLA_MAIN_KEYS:
            self.keytable[f"D-{key}"] = self._key_down(key)
            self.keytable[f"U-{key}"] = self._key_up(key)


def configure(keymap):
    logger.info("NICOLA: configure() start")
    try:
        # nicolaエミュレーターをつくる
        # windows個別、mac個別、nicola共通にわけ、win/macを自動判定して切り替える
        #
        # nicola共通
        # <無変換>: 英数モード時: かなモードへ、入力中: 左親指キーおよび、ひらがな・カタカナトグル変換
        # <変換>: 英数モード時: かなモードへ、入力中: 右親指キーおよび、変換
        # <英数>: かなモード時: 英数モードへ
        #
        # windwos個別
        # 物理の無変換キーを<無変換>
        # 物理の変換キーを<変換>
        # 物理の英数キーを<英数>
        #
        # mac個別
        # 物理の英数キーを<無変換>
        # 物理のかなキーを<変換>
        # 物理の英数キーを<英数>（ただし未確定文字がない場合）

        os_name = platform.system().lower()
        logger.info(f"NICOLA: profile={os_name}")

        keytable_global = keymap.define_keytable(focus_path_pattern="*")
        NicolaEngine(keymap, keytable_global, os_name)

        logger.info("NICOLA: configure() completed")
    except Exception as e:
        logger.info(f"NICOLA: configure() failed: {e}")
        logger.info(traceback.format_exc())
        raise

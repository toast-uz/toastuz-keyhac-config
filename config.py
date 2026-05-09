import platform
import time
import traceback

from keyhac import *
try:
    import pyauto
except Exception:
    pyauto = None


class _FallbackLogger:
    def _log(self, level, msg):
        print(f"{level}: {msg}")
    def info(self, msg): self._log("INFO", msg)
    def warning(self, msg): self._log("WARNING", msg)
    def error(self, msg): self._log("ERROR", msg)


# =====================================================
# NICOLA constants
# =====================================================

# 同時打鍵判定幅（秒）
SIMULT_WINDOW_SEC = 0.18
# 左親指はやや広めに判定
LEFT_SIMULT_WINDOW_SEC = 0.28
# 左親指単打（英数キー兼用）の遅延確定幅（秒）
LEFT_ONESHOT_DELAY_SEC = 0.25
# 英数切替直後にIME反映が遅れるアプリ向けの保護時間
EISU_GUARD_SEC = 0.35

# IME モード（環境差があるため内部状態も併用）
IME_MODE_EISU = 0
IME_MODE_KANA = 1

# 物理キー名（OSにより切替）
# keyhac 1.x(Windows) では日本語キー名が異なるため VKコード表記を使う
# - 変換: VK_CONVERT(28)
# - 無変換: VK_NONCONVERT(29)
# - 英数相当: VK_KANJI(25) を利用（環境により未搭載の場合あり）
WIN_MUHENKAN = "(29)"
WIN_HENKAN = "(28)"
WIN_EISU = "(25)"
MAC_LEFT_THUMB = "Eisu"
MAC_RIGHT_THUMB = "Kana"
MAC_EISU = "Eisu"
MAC_RIGHT_THUMB_SINGLE_CONVERT_KEY = None
MAC_TOGGLE_KEYS = ["Ctrl-J", "Kana"]

# NICOLA 同時打鍵対象キー
NICOLA_MAIN_KEYS = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Minus",
    "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P",
    "Atmark", "OpenBracket", "CloseBracket",
    "A", "S", "D", "F", "G", "H", "J", "K", "L", "Semicolon",
    "Quote",
    "Z", "X", "C", "V", "B", "N", "M", "Comma", "Period", "Slash", "BackSlash",
]

# NICOLA かな 3面テーブル（無/左/右）
NICOLA_TABLE = {
    # 数字段（NICOLA J型）
    "1": ("１", "？", "？"),
    "2": ("２", "／", "／"),
    "3": ("３", "～", "～"),
    "4": ("４", "「", "「"),
    "5": ("５", "」", "」"),
    "6": ("６", "〔", "〔"),
    "7": ("７", "〕", "〕"),
    "8": ("８", "（", "（"),
    "9": ("９", "）", "）"),
    "0": ("０", "『", "『"),
    "Minus": ("－", "』", "』"),
    # 上段
    "Q": ("。", "ぁ", "゜"), "W": ("か", "え", "が"), "E": ("た", "り", "だ"),
    "R": ("こ", "ゃ", "ご"), "T": ("さ", "れ", "ざ"), "Y": ("ら", "ぱ", "よ"),
    "U": ("ち", "ぢ", "に"), "I": ("く", "ぐ", "る"), "O": ("つ", "づ", "ま"),
    "P": ("，", "ぴ", "ぇ"), "Atmark": ("゛", None, "゜"),
    "OpenBracket": (None, None, None),
    # ホーム段
    "A": ("う", "を", "ヴ"), "S": ("し", "あ", "じ"),
    "D": ("て", "な", "で"), "F": ("け", "ゅ", "げ"), "G": ("せ", "も", "ぜ"),
    "H": ("は", "ば", "み"), "J": ("と", "ど", "お"), "K": ("き", "ぎ", "の"),
    "L": ("い", "ぽ", "ょ"), "Semicolon": ("ん", None, "っ"),
    "Quote": ("、", None, None),
    # 下段
    "Z": ("．", "ぅ", None),
    "X": ("ひ", "ー", "び"), "C": ("す", "ろ", "ず"), "V": ("ふ", "や", "ぶ"),
    "B": ("へ", "ぃ", "べ"), "N": ("め", "ぷ", "ぬ"), "M": ("そ", "ぞ", "ゆ"),
    "Comma": ("ね", "ぺ", "む"), "Period": ("ほ", "ぼ", "わ"), "Slash": ("・", "ぉ", None),
    "CloseBracket": (None, None, None), "BackSlash": (None, None, None),
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

# mac で文字直送できない記号・全角数字をキー送信へ変換
MAC_CHAR_KEY_MAP = {
    "１": "1", "２": "2", "３": "3", "４": "4", "５": "5",
    "６": "6", "７": "7", "８": "8", "９": "9", "０": "0",
    "－": "Minus",
    "？": "Shift-Slash",
    "／": "Slash",
    "～": "Shift-Caret",
    "「": "Shift-OpenBracket",
    "」": "Shift-CloseBracket",
    "〔": "OpenBracket",
    "〕": "CloseBracket",
    "（": "Shift-8",
    "）": "Shift-9",
    "『": "Shift-Comma",
    "』": "Shift-Period",
    "，": "Comma",
    "．": "Period",
    "゛": "Atmark",
    "゜": "Shift-Atmark",
}

try:
    logger = getLogger("Config")
except Exception:
    logger = _FallbackLogger()


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
        self.ignore_next_left_thumb_oneshot = False
        self.suppress_next_eisu_oneshot = False
        self.suppress_next_eisu_oneshot_until = 0.0
        self.suppress_next_right_thumb_oneshot = False
        self.force_eisu_until = 0.0
        self.logical_eisu_mode = False
        self.last_eisu_oneshot_at = 0.0

        self._setup()

    def _bind_windows_legacy(self):
        # keyhac 1.83 向け: 無変換/変換を User modifier 化して U0/U1 同時打鍵で扱う
        if hasattr(self.keymap, "defineModifier"):
            self.keymap.defineModifier(self.left_thumb, "User0")
            self.keymap.defineModifier(self.right_thumb, "User1")

        def bind(expr, fn):
            self.keytable[expr] = fn

        # 平打ち
        for key in NICOLA_MAIN_KEYS:
            bind(key, (lambda k=key: self._emit_key(k, None)))

        # 同時打鍵（左/右）
        for key in NICOLA_MAIN_KEYS:
            bind(f"U0-{key}", (lambda k=key: self._emit_key(k, 0)))
            bind(f"U1-{key}", (lambda k=key: self._emit_key(k, 1)))

        # 単打
        bind(f"O-{self.left_thumb}", lambda: self._thumb_stop(0))
        bind(f"O-{self.right_thumb}", lambda: self._thumb_stop(1))
        bind(f"O-{self.eisu_key}", self._eisu_oneshot)

    def _send(self, *keys):
        # keyhac mac (snake_case) / keyhac windows (camelCase) 互換
        if hasattr(self.keymap, "get_input_context"):
            with self.keymap.get_input_context() as input_ctx:
                for k in keys:
                    input_ctx.send_key(k)
            return

        # keyhac 1.x (Windows)
        if hasattr(self.keymap, "beginInput"):
            self.keymap.beginInput()
            for k in keys:
                self.keymap.setInput_FromString(str(k))
            self.keymap.endInput()
            if hasattr(self.keymap, "fixFunnyModifierState"):
                self.keymap.fixFunnyModifierState()
            elif hasattr(self.keymap, "_fixFunnyModifierState"):
                self.keymap._fixFunnyModifierState()
            return

        # Last resort
        for k in keys:
            try:
                cmd = self.keymap.InputKeyCommand(str(k))
                cmd()
            except Exception:
                logger.warning(f"NICOLA: cannot send key '{k}'")

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
            # 記号・全角数字などは直接テキスト送出
            self._send_text(kana)
            return

        for c in seq:
            self._send(ROMAJI_KEYNAME_MAP.get(c, c.upper()))

    def _send_text(self, text):
        # mac: まずキー送信に変換を試す（clipboard禁止のため）
        if self.os_name != "windows":
            key_expr = MAC_CHAR_KEY_MAP.get(text)
            if key_expr:
                self._send(key_expr)
                return

        last_error = None

        # Windows keyhac 1.x
        try:
            if hasattr(self.keymap, "InputTextCommand"):
                self.keymap.InputTextCommand(text)()
                return
        except Exception as e:
            last_error = e

        # Fallback: beginInput + pyauto.Char (clipboardは使わない)
        try:
            if pyauto is not None and hasattr(self.keymap, "beginInput") and hasattr(self.keymap, "endInput"):
                self.keymap.beginInput()
                if hasattr(self.keymap, "setInput_Modifier"):
                    self.keymap.setInput_Modifier(0)
                for ch in text:
                    self.keymap.input_seq.append(pyauto.Char(ch))
                self.keymap.endInput()
                if hasattr(self.keymap, "fixFunnyModifierState"):
                    self.keymap.fixFunnyModifierState()
                elif hasattr(self.keymap, "_fixFunnyModifierState"):
                    self.keymap._fixFunnyModifierState()
                return
        except Exception as e:
            last_error = e

        if pyauto is None:
            logger.info("NICOLA: text send failed because pyauto is unavailable")
        logger.info(f"NICOLA: text send failed '{text}' err={last_error}")

    def _set_ime_kana(self):
        self._send(self.kana_on_key)
        self.ime = True
        self.logical_eisu_mode = False

    def _set_ime_eisu(self):
        self._send(self.eisu_on_key)
        self.ime = False
        self.force_eisu_until = time.time() + EISU_GUARD_SEC
        self.logical_eisu_mode = True

    def _send_ascii_key(self, key_expr):
        was_kana = self._is_kana_mode()
        if was_kana:
            self._set_ime_eisu()
        self._send(key_expr)
        if was_kana:
            self._set_ime_kana()

    def _has_marked_text(self):
        # macOSのアクセシビリティ属性から未確定文字の有無を推定
        try:
            elm = getattr(self.keymap, "focus", None)
            if not elm:
                return False
            names = elm.get_attribute_names()
            if "AXMarkedText" in names:
                marked = elm.get_attribute_value("AXMarkedText")
                return bool(marked)
        except Exception:
            pass
        return False

    def _is_kana_mode(self):
        # 取得できる場合は実IME状態を優先。
        # ただし値域が環境差で不定な場合は内部状態にフォールバックする。
        try:
            wnd = None
            if hasattr(self.keymap, "getWindow"):
                wnd = self.keymap.getWindow()
            elif hasattr(self.keymap, "get_window"):
                wnd = self.keymap.get_window()
            if wnd and hasattr(wnd, "getImeStatus"):
                status = wnd.getImeStatus()
                if status == IME_MODE_EISU:
                    return False
                if status == IME_MODE_KANA:
                    return True
        except Exception:
            pass
        return self.ime

    def _apply_left_oneshot_if_due(self):
        if not self.left_oneshot_pending:
            return
        if self.left_oneshot_at is None:
            return
        if time.time() - self.left_oneshot_at < LEFT_ONESHOT_DELAY_SEC:
            return

        if not self._is_kana_mode():
            self._set_ime_kana()
        else:
            # macではトグルを諦める。windowsでは左親指単打でトグルする。
            if self.os_name == "windows":
                self._send_first(self.toggle_keys)

        self.left_oneshot_pending = False
        self.left_oneshot_at = None

    def _emit_key(self, key, side):
        is_kana = self._is_kana_mode()
        if time.time() <= self.force_eisu_until:
            is_kana = False
        if self.logical_eisu_mode and side is None:
            is_kana = False
        self.ime = is_kana
        table = NICOLA_TABLE.get(key)
        if not table:
            self._send(key)
            return

        # 英数モードでは、親指同時打鍵なし（平打ち）は通常の英数入力を優先する
        if (not is_kana) and (side is None):
            self._send(key)
            return

        kana = table[0]
        if side == 0:
            kana = table[1]
        elif side == 1:
            kana = table[2]

        if not kana:
            return

        if kana.startswith("KEY_ASCII:"):
            self._send_ascii_key(kana[len("KEY_ASCII:"):])
            return

        if kana.startswith("KEY:"):
            self._send(kana[4:])
            return

        if not is_kana:
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
        simult_window = LEFT_SIMULT_WINDOW_SEC if idx == 0 else SIMULT_WINDOW_SEC
        if self.pending_key and self.pending_key_time and now - self.pending_key_time <= simult_window:
            self._emit_key(self.pending_key, idx)
            self.pending_key = None
            self.pending_key_time = None
            self.suppress_oneshot[idx] = True
            if idx == 0:
                self.suppress_next_eisu_oneshot = True
                self.suppress_next_eisu_oneshot_until = time.time() + 0.25
            elif idx == 1:
                self.suppress_next_right_thumb_oneshot = True
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
            # Eisu単打直後の左親指単打遅延発火を抑止
            if (time.time() - self.last_eisu_oneshot_at) <= 0.30:
                self.left_oneshot_pending = False
                self.left_oneshot_at = None
                return
            if self.ignore_next_left_thumb_oneshot:
                self.ignore_next_left_thumb_oneshot = False
                self.left_oneshot_pending = False
                self.left_oneshot_at = None
                return
            # 英数モード -> かなモード は即時反応
            # （遅延確定だと次キーイベント待ちになって切替不能に見えるため）
            if not self._is_kana_mode():
                self._set_ime_kana()
            else:
                # かなモード中のトグルだけ遅延確定
                self.left_oneshot_pending = True
                self.left_oneshot_at = time.time()
        else:
            if self.suppress_next_right_thumb_oneshot:
                self.suppress_next_right_thumb_oneshot = False
                return
            # 右親指単独打鍵: かなモードへ
            if not self._is_kana_mode():
                self._set_ime_kana()

    def _eisu_oneshot(self):
        self._apply_left_oneshot_if_due()
        if self.suppress_next_eisu_oneshot:
            if time.time() <= self.suppress_next_eisu_oneshot_until:
                self.suppress_next_eisu_oneshot = False
                self.suppress_next_eisu_oneshot_until = 0.0
                return
            self.suppress_next_eisu_oneshot = False
            self.suppress_next_eisu_oneshot_until = 0.0
        # macでは英数キーが左親指キーと兼用のため、
        # この単打後に左親指単打処理が走らないよう抑止する。
        self.last_eisu_oneshot_at = time.time()
        self.ignore_next_left_thumb_oneshot = True
        self.left_oneshot_pending = False
        self.left_oneshot_at = None
        # macではトグル運用をしないため、英数キー単打は常に英数モードへ。
        # windows側のみ、未確定文字がある場合はトグル分岐を許可する。
        if self.os_name == "windows" and self._has_marked_text():
            self._send_first(self.toggle_keys)
            return
        self._set_ime_eisu()

    def _key_down(self, key):
        def _f():
            self._apply_left_oneshot_if_due()
            self._apply_pending_plain()
            now = time.time()

            # 親指先押し -> 文字後押し の同時打鍵を優先判定
            if self.shift_down[0] and self.shift_time[0] and now - self.shift_time[0] <= LEFT_SIMULT_WINDOW_SEC:
                self._emit_key(key, 0)
                self.suppress_oneshot[0] = True
                self.suppress_next_eisu_oneshot = True
                self.suppress_next_eisu_oneshot_until = time.time() + 0.25
                self.left_oneshot_pending = False
                self.left_oneshot_at = None
                logger.info(f"NICOLA: emit left {key} (thumb-first)")
                return
            if self.shift_down[1] and self.shift_time[1] and now - self.shift_time[1] <= SIMULT_WINDOW_SEC:
                self._emit_key(key, 1)
                self.suppress_oneshot[1] = True
                self.suppress_next_right_thumb_oneshot = True
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

        # Windows keyhac 1.83 は U0/U1 方式の方が安定
        if self.os_name == "windows" and hasattr(self.keymap, "defineWindowKeymap"):
            self._bind_windows_legacy()
            return

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

        if hasattr(keymap, "define_keytable"):
            keytable_global = keymap.define_keytable(focus_path_pattern="*")
        elif hasattr(keymap, "defineWindowKeymap"):
            keytable_global = keymap.defineWindowKeymap()
        else:
            raise RuntimeError("Unsupported Keyhac API: cannot define keytable")
        NicolaEngine(keymap, keytable_global, os_name)

        logger.info("NICOLA: configure() completed")
    except Exception as e:
        logger.info(f"NICOLA: configure() failed: {e}")
        logger.info(traceback.format_exc())
        raise

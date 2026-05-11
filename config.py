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
# 実験: mac/windows 共通で JISかなキー送出を使う
USE_UNIFIED_JIS_KANA = True
# Windows 英数モード時の文字幅
# "half": 半角英数 (VK_DBE_SBCSCHAR=243)
# "full": 全角英数 (VK_DBE_DBCSCHAR=244)
WINDOWS_EISU_WIDTH = "half"
# Windows の同時打鍵判定方式
# True: keyhac U2/U3（時間定数は効かない）
# False: D/U 自前判定（時間定数が効く）
WINDOWS_USE_LEGACY_U2U3 = False

# 未確定文字（変換前/変換中）時の英数キートグル機能
ENABLE_MARKED_EISU_TOGGLE = True
# state 0 -> 1
MARKED_EISU_TOGGLE_KEY_0 = "Alt-Z"   # ひらがな変換
# state 1 -> 2
MARKED_EISU_TOGGLE_KEY_1 = "Alt-X"   # カタカナ変換
# state 2 -> 3
MARKED_EISU_TOGGLE_KEY_2 = "Fn-F8"    # 半角カタカナ変換
MARKED_EISU_TOGGLE_INITIAL_STATE = 1
# macでAXMarkedTextが取れないアプリ向けの未確定ヒント保持時間

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
    "P": ("，", "ぴ", "ぇ"), "Atmark": ("、", None, "、"),
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
    "Comma": ("ね", "ぺ", "む"), "Period": ("ほ", "ぼ", "わ"), "Slash": ("・", None, "ぉ"),
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

# JISかな入力用: かな1文字 -> 物理キー
# 例: 「お」なら "6"
JIS_KANA_KEY_MAP = {
    "あ": "3", "い": "E", "う": "4", "え": "5", "お": "6",
    "か": "T", "き": "G", "く": "H", "け": "Colon", "こ": "B",
    "さ": "X", "し": "D", "す": "R", "せ": "P", "そ": "C",
    "た": "Q", "ち": "A", "つ": "Z", "て": "W", "と": "S",
    "な": "U", "に": "I", "ぬ": "1", "ね": "Comma", "の": "K",
    "は": "F", "ひ": "V", "ふ": "2", "へ": "Caret", "ほ": "Minus",
    "ま": "J", "み": "N", "む": "CloseBracket", "め": "Slash", "も": "M",
    "や": "7", "ゆ": "8", "よ": "9",
    "ら": "O", "り": "L", "る": "Period", "れ": "Semicolon", "ろ": "Underscore",
    "わ": "0", "を": "Shift-0", "ん": "Y",
    "ぁ": "Shift-3", "ぃ": "Shift-E", "ぅ": "Shift-4", "ぇ": "Shift-5", "ぉ": "Shift-6",
    "ゃ": "Shift-7", "ゅ": "Shift-8", "ょ": "Shift-9", "っ": "Shift-Z",
    "ー": "BackSlash",
    "゛": "Atmark", "゜": "OpenBracket",
    "，": "Shift-Comma", "．": "Shift-Period",
    "、": "Shift-Comma", "。": "Shift-Period", "・": "Shift-Slash",
}


DAKUTEN_BASE_MAP = {
    "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
    "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
    "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
    "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
    "ゔ": "う", "ヴ": "う",
}

HANDAKUTEN_BASE_MAP = {
    "ぱ": "は", "ぴ": "ひ", "ぷ": "ふ", "ぺ": "へ", "ぽ": "ほ",
}

# JISかな送出では扱いづらい文字は、英数キー送出（必要時のみ一時英数化）で処理
NICOLA_ASCII_FALLBACK_MAP = {
    "１": "1", "２": "2", "３": "3", "４": "4", "５": "5",
    "６": "6", "７": "7", "８": "8", "９": "9", "０": "0",
    "－": "Minus",
}

TOPROW_SYMBOL_ASCII_KEY_MAP = {
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
}
TOPROW_DIRECT_FULLWIDTH_SYMBOLS = set(TOPROW_SYMBOL_ASCII_KEY_MAP.keys())
TOPROW_PLAIN_FULLWIDTH_TEXT_MAP = {
    "1": "１", "2": "２", "3": "３", "4": "４", "5": "５",
    "6": "６", "7": "７", "8": "８", "9": "９", "0": "０",
    "Minus": "－",
}
TOPROW_SHIFT_FULLWIDTH_TEXT_MAP = {
    "1": "！", "2": "／", "3": "～", "4": "「", "5": "」",
    "6": "〔", "7": "〕", "8": "（", "9": "）", "0": "『",
    "Minus": "』",
}

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
    def __init__(self, keymap, keytable, os_name, key_profile=None):
        self.keymap = keymap
        self.keytable = keytable
        self.os_name = os_name

        if os_name == "windows":
            self.left_thumb = WIN_MUHENKAN
            self.right_thumb = WIN_HENKAN
            self.eisu_key = WIN_EISU
            # keyhac 1.83 は Henkan/Muhenkan 文字列名を受け付けないため
            # IME制御キー送出は VK 数値表記で統一する
            self.toggle_key = "(29)"   # 無変換
            self.convert_key = "(28)"  # 変換
            # かなON は「モード固定」系のみ使用する。
            # - VK_IME_ON(22)
            # - VK_KANA(21)
            # Convert/NonConvert をかなON用途に使うと
            # IME設定次第でローマ字/かなトグルに巻き込まれやすい。
            self.kana_on_key = "(22)"  # IME ON
            self.kana_on_keys = ["(22)", "(21)"]  # かなONのフォールバック列
            self.eisu_on_key = "(25)"  # 英数
            self.eisu_width_half_key = "(243)"
            self.eisu_width_full_key = "(244)"
            self.toggle_keys = [self.toggle_key]
        else:
            self.left_thumb = MAC_LEFT_THUMB
            self.right_thumb = MAC_RIGHT_THUMB
            self.eisu_key = MAC_EISU
            self.toggle_key = "Kana"
            self.convert_key = MAC_RIGHT_THUMB_SINGLE_CONVERT_KEY
            self.kana_on_key = "Kana"
            self.kana_on_keys = [self.kana_on_key]
            self.eisu_on_key = "Eisu"
            self.eisu_width_half_key = None
            self.eisu_width_full_key = None
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
        self.input_key_profile = key_profile
        self._is_teams_target = False
        self._teams_target_identity = ""
        self._webview2_mode = False
        self.marked_eisu_toggle_state = MARKED_EISU_TOGGLE_INITIAL_STATE
        self.composing_active = False

        self._setup()

    def _set_input_profile(self, profile):
        if self.input_key_profile == profile:
            return
        self.input_key_profile = profile
        logger.info(f"NICOLA: key-profile={profile}")

    def _ensure_input_profile(self):
        if self.input_key_profile is None:
            self._set_input_profile("windows-vk" if self.os_name == "windows" else "mac")

    def _bind_windows_legacy(self):
        left_mod_vk = 29
        right_mod_vk = 28
        logger.info(
            "NICOLA: windows-thumb-keys "
            f"left=({left_mod_vk}) right=({right_mod_vk}) profile={self.input_key_profile}"
        )
        left_mod_key = f"({left_mod_vk})"
        right_mod_key = f"({right_mod_vk})"

        if hasattr(self.keymap, "defineModifier"):
            # 指示どおり User2/User3 を使用
            self.keymap.defineModifier(left_mod_vk, "User2")
            self.keymap.defineModifier(right_mod_vk, "User3")

        def bind(expr, fn):
            self.keytable[expr] = fn

        # 平打ち（プロファイル固定はしない。親指イベントで確定させる）
        for key in NICOLA_MAIN_KEYS:
            bind(key, (lambda k=key: self._act_plain(k)))

        # 同時打鍵（左/右）
        for key in NICOLA_MAIN_KEYS:
            bind(f"U2-{key}", (lambda k=key: self._act_left(k)))
            bind(f"U3-{key}", (lambda k=key: self._act_right(k)))

        # 単打
        bind(f"O-{left_mod_key}", lambda: self._act_left_oneshot())
        bind(f"O-{right_mod_key}", lambda: self._act_right_oneshot())
        bind(f"O-{self.eisu_key}", lambda: self._act_eisu_oneshot())

        self._bind_toprow_fullwidth(bind)

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

    def _detect_teams_target(self):
        """
        編集対象が Teams かをベストエフォートで判定する。
        挙動は変えず、判定結果はログ用途のみ。
        """
        fields = []
        wnd = None
        try:
            if hasattr(self.keymap, "getWindow"):
                wnd = self.keymap.getWindow()
            elif hasattr(self.keymap, "get_window"):
                wnd = self.keymap.get_window()
        except Exception:
            wnd = None

        if wnd:
            for name in (
                "getProcessName",
                "get_process_name",
                "getClassName",
                "get_class_name",
                "getText",
                "get_text",
            ):
                try:
                    if hasattr(wnd, name):
                        v = getattr(wnd, name)()
                        if v:
                            fields.append(str(v))
                except Exception:
                    pass

        try:
            focus = getattr(self.keymap, "focus", None)
            if focus:
                for attr_name in ("AXTitle", "AXRoleDescription"):
                    try:
                        if hasattr(focus, "get_attribute_value"):
                            v = focus.get_attribute_value(attr_name)
                            if v:
                                fields.append(str(v))
                    except Exception:
                        pass
        except Exception:
            pass

        joined = " | ".join(fields)
        hay = joined.lower()
        is_teams = (
            ("teams" in hay)
            or ("msteams" in hay)
            or ("ms-teams" in hay)
            or ("teams2" in hay)
        )
        return is_teams, joined

    def _refresh_teams_target_state(self):
        is_teams, identity = self._detect_teams_target()
        ident_l = identity.lower()
        webview2_mode = ("msedgewebview2.exe" in ident_l)
        if (is_teams != self._is_teams_target) or (identity != self._teams_target_identity):
            self._is_teams_target = is_teams
            self._teams_target_identity = identity
            self._webview2_mode = webview2_mode
            logger.info(f"NICOLA: webview2-mode={'enable' if self._webview2_mode else 'disable'}")
        else:
            # 状態不変でもモード値は更新しておく（将来の分岐用）
            self._webview2_mode = webview2_mode

    # 共通アクション（入力経路差異を吸収）
    def _act_plain(self, key):
        self._refresh_teams_target_state()
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: plain {key}")
        self._emit_key(key, None)

    def _act_left(self, key):
        self._refresh_teams_target_state()
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: left {key}")
        self._emit_key(key, 0)

    def _act_right(self, key):
        self._refresh_teams_target_state()
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: right {key}")
        self._emit_key(key, 1)

    def _act_left_oneshot(self):
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: left oneshot")
        self._thumb_stop(0)

    def _act_right_oneshot(self):
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: right oneshot")
        self._thumb_stop(1)

    def _act_eisu_oneshot(self):
        self._ensure_input_profile()
        logger.info(f"NICOLA[{self.input_key_profile}]: eisu oneshot")
        self._eisu_oneshot()

    def _act_toprow_plain(self, key_name, ch):
        self._ensure_input_profile()
        if not self._is_kana_mode():
            self._send(key_name)
            return
        self._send_toprow_fullwidth(ch)

    def _act_toprow_shift(self, key_name, ch):
        self._ensure_input_profile()
        if not self._is_kana_mode():
            self._send(f"Shift-{key_name}")
            return
        self._send_toprow_fullwidth(ch)

    def _act_toprow_shift_with_key(self, key_name, ch):
        self._ensure_input_profile()
        if not self._is_kana_mode():
            self._send(f"Shift-{key_name}")
            return
        if self._send_text(ch, prefer_key_on_mac=False):
            return
        if USE_UNIFIED_JIS_KANA:
            # JISかな統一モードでは従来動作（全角寄せ）を維持
            self._send_ascii_key_fullwidth(f"Shift-{key_name}")
        else:
            # ローマ字かなモードではIMEモードを触らず Shift+上段キーを送る
            self._send(f"Shift-{key_name}")

    def _act_commit_clear_and_send(self, key_name):
        self._reset_marked_eisu_toggle_if_needed()
        self._send(key_name)

    def _act_backspace_with_compose_check(self):
        self._reset_marked_eisu_toggle_if_needed()
        self._send("Back")

    def _bind_toprow_fullwidth(self, bind):
        # 上段: 単独打鍵/通常Shift打鍵を全角送出で補強（mac/windows共通）
        for k, ch in TOPROW_PLAIN_FULLWIDTH_TEXT_MAP.items():
            bind(k, (lambda key=k, c=ch: self._act_toprow_plain(key, c)))
        for k, ch in TOPROW_SHIFT_FULLWIDTH_TEXT_MAP.items():
            bind(f"Shift-{k}", (lambda key=k, c=ch: self._act_toprow_shift_with_key(key, c)))
        # 確定/キャンセル系キーで composing 状態を即座にクリア
        bind("Return", (lambda: self._act_commit_clear_and_send("Return")))
        bind("Enter", (lambda: self._act_commit_clear_and_send("Enter")))
        bind("Escape", (lambda: self._act_commit_clear_and_send("Escape")))
        # 未確定文字をBackspaceで消し切った場合の compose 解除を補助
        bind("Back", self._act_backspace_with_compose_check)

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

    def _send_jis_kana(self, kana):
        if kana in TOPROW_DIRECT_FULLWIDTH_SYMBOLS:
            if self._send_text(kana, prefer_key_on_mac=False):
                return True
            top_sym_fb = TOPROW_SYMBOL_ASCII_KEY_MAP.get(kana)
            if top_sym_fb:
                logger.info(f"NICOLA: direct text failed for '{kana}', fallback key={top_sym_fb}")
                self._send_ascii_key_fullwidth(top_sym_fb)
                return True
            return False

        top_sym = TOPROW_SYMBOL_ASCII_KEY_MAP.get(kana)
        if top_sym:
            self._send_ascii_key_fullwidth(top_sym)
            return True

        ascii_key = NICOLA_ASCII_FALLBACK_MAP.get(kana)
        if ascii_key:
            self._send_ascii_key(ascii_key)
            return True

        if kana == "ー":
            # JISかな入力で長音「ー」は ¥(Yen) キー
            self._send("Yen")
            return True

        key_expr = JIS_KANA_KEY_MAP.get(kana)
        if key_expr:
            self._send(key_expr)
            return True

        base = DAKUTEN_BASE_MAP.get(kana)
        if base:
            base_key = JIS_KANA_KEY_MAP.get(base)
            if base_key:
                self._send(base_key)
                self._send(JIS_KANA_KEY_MAP["゛"])
                return True

        base = HANDAKUTEN_BASE_MAP.get(kana)
        if base:
            base_key = JIS_KANA_KEY_MAP.get(base)
            if base_key:
                self._send(base_key)
                self._send(JIS_KANA_KEY_MAP["゜"])
                return True

        return False

    def _send_toprow_fullwidth(self, ch):
        if self._send_text(ch, prefer_key_on_mac=False):
            return
        key_expr = TOPROW_SYMBOL_ASCII_KEY_MAP.get(ch)
        if key_expr:
            self._send_ascii_key_fullwidth(key_expr)

    def _set_composing_active(self, active):
        self.composing_active = bool(active)

    def _reset_marked_eisu_toggle_if_needed(self):
        if self.marked_eisu_toggle_state != MARKED_EISU_TOGGLE_INITIAL_STATE:
            self.marked_eisu_toggle_state = MARKED_EISU_TOGGLE_INITIAL_STATE
            logger.info(f"NICOLA: marked-eisu-toggle reset -> {MARKED_EISU_TOGGLE_INITIAL_STATE}")
        self._set_composing_active(False)

    def _run_marked_eisu_toggle(self):
        state = self.marked_eisu_toggle_state
        if state >= 3:
            state = 0
            self.marked_eisu_toggle_state = 0
        key_expr = None
        if state == 0:
            key_expr = MARKED_EISU_TOGGLE_KEY_0
        elif state == 1:
            key_expr = MARKED_EISU_TOGGLE_KEY_1
        elif state == 2:
            key_expr = MARKED_EISU_TOGGLE_KEY_2

        try:
            if key_expr:
                self._send(key_expr)
            self.marked_eisu_toggle_state = min(state + 1, 3)
            logger.info(
                f"NICOLA: marked-eisu-toggle state={state} key={key_expr} -> {self.marked_eisu_toggle_state}"
            )
            return True
        except Exception as e:
            logger.info(f"NICOLA: marked-eisu-toggle send failed key={key_expr} err={e}")
            return False

    def _send_text(self, text, prefer_key_on_mac=True):
        # mac: 必要時のみキー送信に変換を試す（clipboard禁止のため）
        if self.os_name != "windows" and prefer_key_on_mac:
            key_expr = MAC_CHAR_KEY_MAP.get(text)
            if key_expr:
                self._send(key_expr)
                return True

        last_error = None

        # keyhac mac: input context の send_text が使える場合は最優先
        try:
            if hasattr(self.keymap, "get_input_context"):
                with self.keymap.get_input_context() as input_ctx:
                    if hasattr(input_ctx, "send_text"):
                        input_ctx.send_text(text)
                        return True
        except Exception as e:
            last_error = e

        # Windows keyhac 1.x
        try:
            if hasattr(self.keymap, "InputTextCommand"):
                self.keymap.InputTextCommand(text)()
                return True
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
                return True
        except Exception as e:
            last_error = e

        if pyauto is None:
            logger.info("NICOLA: text send failed because pyauto is unavailable")
        logger.info(f"NICOLA: text send failed '{text}' err={last_error}")
        return False

    def _set_ime_kana(self):
        if self.os_name == "windows":
            ok = self._send_first(self.kana_on_keys)
            logger.info(
                "NICOLA: set_ime_kana windows "
                f"result={ok} keys={self.kana_on_keys}"
            )
        else:
            self._send(self.kana_on_key)
        self.ime = True
        self.logical_eisu_mode = False

    def _set_ime_eisu(self):
        self._send(self.eisu_on_key)
        if self.os_name == "windows":
            if WINDOWS_EISU_WIDTH == "full":
                if self.eisu_width_full_key:
                    self._send(self.eisu_width_full_key)
            else:
                if self.eisu_width_half_key:
                    self._send(self.eisu_width_half_key)
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

    def _send_ascii_key_fullwidth(self, key_expr):
        was_kana = self._is_kana_mode()
        if was_kana:
            self._set_ime_eisu()
        if self.os_name == "windows" and self.eisu_width_full_key:
            self._send(self.eisu_width_full_key)
        self._send(key_expr)
        if was_kana:
            self._set_ime_kana()

    def _has_marked_text(self):
        # 未確定文字(候補)の有無を推定
        # macOS: AXMarkedText
        # Windows: keyhac 1.83 では明確な候補APIがないため False 扱い
        if self.os_name == "windows":
            return False
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

    def _is_preedit_active_for_toggle(self):
        if self.os_name == "windows":
            return False
        if self._has_marked_text():
            return True
        return self.composing_active

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
        # 通常入力が進んだら、未確定時英数トグル状態はリセット
        self._reset_marked_eisu_toggle_if_needed()
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
        if USE_UNIFIED_JIS_KANA:
            if self._send_jis_kana(kana):
                self._set_composing_active(True)
                return
        self._send_romaji(kana)
        self._set_composing_active(True)

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
            # 無変換:
            # - 英数時: かなモードへ遷移
            # - かな時: かなトグル
            if self.os_name == "windows":
                if self._is_kana_mode():
                    self._send_first(self.toggle_keys)
                else:
                    self._set_ime_kana()
            else:
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
            # 変換:
            # - Windows は入力モードを不用意に触らず、変換キーのみ送出
            if self.os_name == "windows":
                if self.convert_key:
                    self._send(self.convert_key)
            else:
                # mac: 未確定文字がある場合は変換、なければかなモードへ
                if self._has_marked_text():
                    if self.convert_key:
                        self._send(self.convert_key)
                else:
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
        if self.os_name != "windows" and ENABLE_MARKED_EISU_TOGGLE and self._is_preedit_active_for_toggle():
            if self._run_marked_eisu_toggle():
                return
        self._reset_marked_eisu_toggle_if_needed()
        # 英数は常に英数モードへ
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
        logger.info(f"NICOLA: unified-jis-kana-send={USE_UNIFIED_JIS_KANA}")
        logger.info(f"NICOLA: windows-simult-mode={'legacy-u2u3' if WINDOWS_USE_LEGACY_U2U3 else 'timed-du'}")
        logger.info(
            "NICOLA: physical keys "
            f"left={self.left_thumb}, right={self.right_thumb}, eisu={self.eisu_key}"
        )
        if self.os_name == "windows":
            logger.info("NICOLA: windows-candidate-detect=limited(false-by-default)")
        self._refresh_teams_target_state()
        if self.os_name != "windows":
            self._set_input_profile("mac")

        # Windows: legacy U2/U3 を使う場合のみこちらに入る
        if (
            self.os_name == "windows"
            and WINDOWS_USE_LEGACY_U2U3
            and hasattr(self.keymap, "defineWindowKeymap")
        ):
            self._bind_windows_legacy()
            return

        # non-legacy（主に mac）でも上段の単独/Shiftを同じ全角ルートへ
        def bind(expr, fn):
            self.keytable[expr] = fn
        self._bind_toprow_fullwidth(bind)

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
        key_profile = None
        if os_name == "windows":
            key_profile = "windows-vk"
            logger.info("NICOLA: windows-key-profile=fixed(windows-vk)")

        if hasattr(keymap, "define_keytable"):
            keytable_global = keymap.define_keytable(focus_path_pattern="*")
        elif hasattr(keymap, "defineWindowKeymap"):
            keytable_global = keymap.defineWindowKeymap()
        else:
            raise RuntimeError("Unsupported Keyhac API: cannot define keytable")
        NicolaEngine(keymap, keytable_global, os_name, key_profile=key_profile)

        logger.info("NICOLA: configure() completed")
    except Exception as e:
        logger.info(f"NICOLA: configure() failed: {e}")
        logger.info(traceback.format_exc())
        raise

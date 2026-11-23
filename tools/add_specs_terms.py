"""Term table for AT spec sheets / model-name strings."""
NAMES = [('ベルゼルガBTS　“ブルーナイト”', 'Berserga BTS "Blue Knight"'),
         ('スコープドッグ', 'Scopedog'), ('マーシィドッグ', 'Mercydog'), ('パープルベア', 'Purple Bear'),
         ('ストロングバックス', 'Strong Bacchus'), ('ファッティー', 'Fatty'), ('エクルビス', 'Ecrevisse'),
         ('ツヴァーク', 'Zwerg'), ('ラビドリードッグ', 'Rabidlydog'), ('ブラッドサッカー', 'Bloodsucker'),
         ('エルドスピーネ', 'Erdspinne'), ('オーデルバックラー', 'Oder Buckler'), ('ストライクドッグ', 'Strikedog'),
         ('ブルーティッシュドッグ', 'Brutishdog'), ('ライトスコープドッグ', 'Light Scopedog'),
         ('ベルゼルガ・イミテイト', 'Berserga Imitate'), ('ダイビングビートル', 'Diving Beetle'),
         ('スタンディングトータス', 'Standing Tortoise'), ('スタンディングタートル', 'Standing Turtle'),
         ('スナッピングタートル', 'Snapping Turtle'), ('ベルゼルガＤＴ', 'Berserga DT'), ('ベルゼルガＷＰ', 'Berserga WP'),
         ('バーグラリードッグ', 'Burglarydog'), ('シャドウフレア', 'Shadow Flare'), ('デスメッセンジャー', 'Death Messenger'),
         ('レッドショルダー・カスタム', 'Red Shoulder Custom'), ('レッドショルダーカスタム', 'Red Shoulder Custom'),
         ('ＲＳターボカスタム', 'RS Turbo Custom'), ('ターボカスタム', 'Turbo Custom'),
         ('（戦艦Ｘ搭載仕様）', ' (Battleship X Spec)'), ('（陸戦用Ａ型）', ' (Ground Type A)'), ('（陸戦用Ｂ型）', ' (Ground Type B)'),
         ('（ペールゼン・ファイルズ）', '(The Pailsen Files)'), ('（フォークトカスタム）', ' (Vogt Custom)'),
         ('(パラシュートザック装備）', '(Parachute Sack)'), ('（コニンカラー）', ' (Konin Colors)'), ('（オリヤカラー）', ' (Oriya Colors)'),
         ('・キリコ機', ' Chirico Unit'), ('（オドン戦）', '(Odon Battle)'), ('（グレゴルー機）', ' (Grego)'),
         ('（ムーザ機）', ' (Mousa)'), ('（バイマン機）', ' (Baiman)'), ('（キリコ機）', ' (Chirico)'), ('（リーマン機）', '(Riemann)'),
         ('（ラウンドムーバー付）', '(w/ Round Mover)'), ('（メルキアカラー）', ' (Melkia Colors)')]
TERMS = [('基本待機重量', 'Weight'), ('巡航走行速度', 'Cruise Speed'), ('標準交換時間', 'PR Swap'),
         ('PR液総量', 'PR Volume'), ('PR液', 'PR Fluid'), ('全高', 'Height'), ('装甲厚', 'Armor'),
         ('固定武装', 'Fixed Arms'), ('11ミリ3連装機関銃', '11mm Triple MG'), ('11ミリ機関銃', '11mm MG'),
         ('スモークディスチャージャー', 'Smoke Discharger'), ('アームパンチ', 'Arm Punch'),
         ('パイルバンカー', 'Pile Bunker'), ('なし', 'None'), ('リットル', 'L'),
         ('：', ':'), ('～', '-'), ('－', '-'), ('・', '-'), ('Ⅱ', 'II'), ('×', 'x'), ('　', ' '),
         ('Ａ', 'A'), ('Ｓ', 'S'), ('Ｘ', 'X')]
def tr_spec(txt):
    if txt == '%d体':
        return '%d'
    if 'SPEC.' not in txt and not txt.split('\n')[0].replace('-', '').isascii():
        return None
    for a, b in NAMES + TERMS:
        txt = txt.replace(a, b)
    if not txt.isascii():
        return None
    return txt.replace('\n', '|')

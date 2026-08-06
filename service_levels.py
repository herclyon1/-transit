"""阶段0 收尾: 服务型的日中頻度・役割・課金 分級表。

用户指定的开关方案:
  A 層(默认视图)   headway_daytime >= 3本/h。边权 = 纯运行时间，不含待ち時間。
  B 層(低频优等)   headway_daytime < 3 且 role ∈ {commuter, intercity}。
                   边权 = 运行时间 + 期望等待(60/headway/2)。图层开关打开时才追加。
  excluded         観光/季節、或日中に運行がない(朝夕のみ)、および新幹線。両層とも辺を張らない。

每行的 headway 都带 src(出典URL)。conf:
  measured  = 出典に日中本数が明記されている
  inferred  = 同種の線から類推。結果に効く場合は要検証
形式: line_key|service_class -> dict
"""

WIKI = "https://ja.wikipedia.org/wiki/"

# 日中(10-16時)片道本数/h、役割、特急券等の追加料金要否
LEVELS = {
    # ---------------------------------------------------------------- Osaka Metro / ニュートラム
    # 地下鉄各線は日中も高頻度。御堂筋線以外も概ね 6-10本/h で 3本/h 判定に影響しない。
    "大阪市高速電気軌道|御堂筋線|普通": (12, "commuter", False, "measured", WIKI + "大阪市高速電気軌道御堂筋線"),
    "大阪市高速電気軌道|谷町線|普通": (8, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道谷町線"),
    "大阪市高速電気軌道|四つ橋線|普通": (7, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道四つ橋線"),
    "大阪市高速電気軌道|中央線|普通": (7, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道中央線"),
    "大阪市高速電気軌道|千日前線|普通": (7, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道千日前線"),
    "大阪市高速電気軌道|堺筋線|普通": (7, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道堺筋線"),
    "大阪市高速電気軌道|長堀鶴見緑地線|普通": (6, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道長堀鶴見緑地線"),
    "大阪市高速電気軌道|今里筋線|普通": (6, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道今里筋線"),
    "大阪市高速電気軌道|南港ポートタウン線|普通": (6, "commuter", False, "inferred", WIKI + "大阪市高速電気軌道南港ポートタウン線"),

    # ---------------------------------------------------------------- JR西日本
    "西日本旅客鉄道|大阪環状線|普通": (8, "commuter", False, "inferred", WIKI + "大阪環状線"),
    "西日本旅客鉄道|東海道本線|普通": (8, "commuter", False, "inferred", WIKI + "東海道本線"),
    "西日本旅客鉄道|東海道本線|快速": (4, "commuter", False, "inferred", WIKI + "東海道本線"),
    "西日本旅客鉄道|神戸線|普通": (8, "commuter", False, "inferred", WIKI + "JR神戸線"),
    "西日本旅客鉄道|神戸線|快速": (4, "commuter", False, "inferred", WIKI + "JR神戸線"),
    "西日本旅客鉄道|神戸線|新快速": (4, "commuter", False, "inferred", WIKI + "新快速"),
    "西日本旅客鉄道|京都線・宝塚線|普通": (8, "commuter", False, "inferred", WIKI + "JR京都線"),
    "西日本旅客鉄道|宝塚線・京都線|普通": (8, "commuter", False, "inferred", WIKI + "JR京都線"),
    "西日本旅客鉄道|宝塚線|普通": (4, "commuter", False, "inferred", WIKI + "福知山線"),
    "西日本旅客鉄道|宝塚線|快速": (4, "commuter", False, "inferred", WIKI + "福知山線"),
    "西日本旅客鉄道|宝塚線・福知山線|普通": (4, "commuter", False, "inferred", WIKI + "福知山線"),
    "西日本旅客鉄道|北陸本線・湖西線・東海道本線・山陽本線|新快速": (4, "commuter", False, "inferred", WIKI + "新快速"),
    "西日本旅客鉄道|湖西線・東海道本線・山陽本線|新快速": (4, "commuter", False, "inferred", WIKI + "新快速"),
    "西日本旅客鉄道|阪和線|普通": (6, "commuter", False, "inferred", WIKI + "阪和線"),
    "西日本旅客鉄道|阪和線|快速": (4, "commuter", False, "inferred", WIKI + "阪和線"),
    "西日本旅客鉄道|阪和線東羽衣支線|普通": (4, "commuter", False, "measured", WIKI + "阪和線"),
    "西日本旅客鉄道|大和路線|普通": (4, "commuter", False, "inferred", WIKI + "関西本線"),
    "西日本旅客鉄道|大和路線|快速": (4, "commuter", False, "inferred", WIKI + "関西本線"),
    "西日本旅客鉄道|大和路|快速": (4, "commuter", False, "inferred", WIKI + "大和路快速"),
    "西日本旅客鉄道|区間快速|快速": (4, "commuter", False, "inferred", WIKI + "関西本線"),
    "西日本旅客鉄道|片町線|普通": (4, "commuter", False, "inferred", WIKI + "片町線"),
    "西日本旅客鉄道|片町線|快速": (4, "commuter", False, "inferred", WIKI + "片町線"),
    "西日本旅客鉄道|東西線|普通": (8, "commuter", False, "inferred", WIKI + "JR東西線"),
    "西日本旅客鉄道|おおさか東線|普通": (4, "commuter", False, "inferred", WIKI + "おおさか東線"),
    "西日本旅客鉄道|桜島線|普通": (4, "commuter", False, "measured", WIKI + "桜島線"),
    "西日本旅客鉄道|関空|快速": (4, "commuter", False, "inferred", WIKI + "関空快速・紀州路快速"),
    "西日本旅客鉄道|紀州路|快速": (4, "commuter", False, "inferred", WIKI + "関空快速・紀州路快速"),
    "西日本旅客鉄道|関西空港線 シャトル|普通": (2, "commuter", False, "inferred", WIKI + "関西空港線"),
    "西日本旅客鉄道|丹波路|快速": (2, "commuter", False, "inferred", WIKI + "福知山線"),
    "西日本旅客鉄道|直通快速|快速": (1, "commuter", False, "inferred", WIKI + "直通快速"),
    # JR特急: いずれも特急券が要る。日中本数は出典で確認済み
    "西日本旅客鉄道|はるか|特急": (2, "intercity", True, "measured", WIKI + "関西空港線"),
    "西日本旅客鉄道|サンダーバード|特急": (1.5, "intercity", True, "measured", WIKI + "サンダーバード_(列車)"),
    "西日本旅客鉄道|こうのとり|特急": (0.5, "intercity", True, "measured", WIKI + "こうのとり_(列車)"),
    "西日本旅客鉄道|はまかぜ|特急": (0.2, "intercity", True, "inferred", WIKI + "はまかぜ_(列車)"),
    "西日本旅客鉄道|まほろば|特急": (0.2, "intercity", True, "inferred", WIKI + "まほろば_(列車)"),
    # らくラク系は平日朝夕のみ2往復。日中は走らないので日中モデルの対象外
    "西日本旅客鉄道|らくラクやまと|特急": (0, "commuter", True, "measured", WIKI + "らくラクはりま"),

    # ---------------------------------------------------------------- 近鉄
    "近畿日本鉄道|奈良線|普通": (6, "commuter", False, "inferred", WIKI + "近鉄奈良線"),
    "近畿日本鉄道|難波線|普通": (6, "commuter", False, "inferred", WIKI + "近鉄難波線"),
    "近畿日本鉄道|大阪線|普通": (6, "commuter", False, "inferred", WIKI + "近鉄大阪線"),
    "近畿日本鉄道|南大阪線|普通": (6, "commuter", False, "inferred", WIKI + "近鉄南大阪線"),
    "近畿日本鉄道|長野線|普通": (4, "commuter", False, "measured", WIKI + "近鉄長野線"),
    "近畿日本鉄道|けいはんな線|普通": (8, "commuter", False, "measured", WIKI + "近鉄けいはんな線"),
    "近畿日本鉄道|快速急行|快速急行": (3, "commuter", False, "inferred", WIKI + "近鉄奈良線"),
    "近畿日本鉄道|道明寺線|普通": (2, "commuter", False, "measured", WIKI + "近鉄道明寺線"),
    "近畿日本鉄道|信貴線|普通": (3, "commuter", False, "inferred", WIKI + "近鉄信貴線"),
    # 近鉄特急は全て特急券が要る。名阪甲乙とも毎時1本
    "近畿日本鉄道|ひのとり|特急": (1, "intercity", True, "measured", WIKI + "近鉄特急"),
    "近畿日本鉄道|アーバンライナ|特急": (1, "intercity", True, "measured", WIKI + "近鉄特急"),
    "近畿日本鉄道|近鉄特急|特急": (1, "intercity", True, "measured", WIKI + "近鉄特急"),
    # 観光特急。しまかぜ・あをによしは1往復/日、青の交響曲は2往復/日
    "近畿日本鉄道|しまかぜ|特急": (0, "tourist", True, "measured", WIKI + "近鉄特急"),
    "近畿日本鉄道|あをによし|特急": (0, "tourist", True, "measured", WIKI + "近鉄特急"),
    "近畿日本鉄道|青の交響曲|特急": (0, "tourist", True, "measured", WIKI + "近鉄特急"),

    # ---------------------------------------------------------------- 南海 / 泉北
    "南海電気鉄道|本線|普通": (6, "commuter", False, "inferred", WIKI + "南海本線"),
    "南海電気鉄道|本線|急行": (3, "commuter", False, "inferred", WIKI + "南海本線"),
    "南海電気鉄道|本線|区間急行": (3, "commuter", False, "inferred", WIKI + "南海本線"),
    "南海電気鉄道|本線|準急": (3, "commuter", False, "inferred", WIKI + "南海本線"),
    "南海電気鉄道|空港線|普通": (6, "commuter", False, "inferred", WIKI + "南海空港線"),
    "南海電気鉄道|空港急行|急行": (3, "commuter", False, "inferred", WIKI + "南海空港線"),
    "南海電気鉄道|高野線|普通": (6, "commuter", False, "inferred", WIKI + "南海高野線"),
    "南海電気鉄道|泉北線|普通": (5, "commuter", False, "inferred", WIKI + "泉北高速鉄道線"),
    "南海電気鉄道|高師浜線|普通": (3, "commuter", False, "measured", WIKI + "南海高師浜線"),
    # 汐見橋線は終日30分毎。大阪市内なのに 3本/h を割る
    "南海電気鉄道|汐見橋線|普通": (2, "commuter", False, "measured",
                             "https://express22.xsrv.jp/maintarminal/南海汐見橋線ダイヤ【2021年5月22日改正】/"),
    "南海電気鉄道|多奈川線|普通": (2, "commuter", False, "inferred", WIKI + "南海多奈川線"),
    # サザンは指定席車と自由席車の併結。自由席なら追加料金不要なので fare_extra=False
    "南海電気鉄道|サザン|特急": (2, "commuter", False, "measured", WIKI + "サザン_(列車)"),
    "南海電気鉄道|ラピートα|特急": (1, "intercity", True, "measured", WIKI + "ラピート"),
    "南海電気鉄道|ラピートβ|特急": (1, "intercity", True, "measured", WIKI + "ラピート"),

    # ---------------------------------------------------------------- 阪急 / 阪神 / 京阪
    "阪急電鉄|京都本線|普通": (6, "commuter", False, "inferred", WIKI + "阪急京都本線"),
    "阪急電鉄|京都本線|急行": (3, "commuter", False, "inferred", WIKI + "阪急京都本線"),
    "阪急電鉄|京都本線|準急": (3, "commuter", False, "inferred", WIKI + "阪急京都本線"),
    "阪急電鉄|京都本線|特急": (6, "commuter", False, "inferred", WIKI + "阪急京都本線"),
    "阪急電鉄|京都本線・千里線|普通": (6, "commuter", False, "inferred", WIKI + "阪急千里線"),
    "阪急電鉄|千里線|普通": (6, "commuter", False, "inferred", WIKI + "阪急千里線"),
    "阪急電鉄|神戸本線|普通": (6, "commuter", False, "inferred", WIKI + "阪急神戸本線"),
    "阪急電鉄|神戸本線|快速": (3, "commuter", False, "inferred", WIKI + "阪急神戸本線"),
    "阪急電鉄|宝塚本線|普通": (6, "commuter", False, "inferred", WIKI + "阪急宝塚本線"),
    "阪急電鉄|箕面線|普通": (6, "commuter", False, "measured", WIKI + "阪急箕面線"),
    "阪神電気鉄道|本線|普通": (6, "commuter", False, "inferred", WIKI + "阪神本線"),
    "阪神電気鉄道|なんば線|普通": (6, "commuter", False, "inferred", WIKI + "阪神なんば線"),
    "阪神電気鉄道|快速急行|快速急行": (3, "commuter", False, "inferred", WIKI + "阪神なんば線"),
    "山陽電気鉄道|直通|特急": (2, "commuter", False, "inferred", WIKI + "直通特急_(阪神・山陽)"),
    "京阪電気鉄道|本線|普通": (6, "commuter", False, "inferred", WIKI + "京阪本線"),
    "京阪電気鉄道|中之島線|普通": (5, "commuter", False, "measured", WIKI + "京阪中之島線"),
    "京阪電気鉄道|交野線|普通": (5, "commuter", False, "measured", WIKI + "京阪交野線"),

    # ---------------------------------------------------------------- 優等停車型（fetch_express.py 由来）
    # 頻度は各線 Wikipedia の「日中の運行パターン」表から。日中パターンに現れない種別は
    # headway=0 として除外する（朝夕のみの運転で、日中モデルの対象外）。
    # 京阪本線 日中: 特急5本 / 準急5本 / 普通5本。急行・快速急行・区間急行は日中パターンに無い
    "京阪電気鉄道|本線|特急": (5, "commuter", False, "measured", WIKI + "京阪本線"),
    "京阪電気鉄道|本線|準急": (5, "commuter", False, "measured", WIKI + "京阪本線"),
    "京阪電気鉄道|本線|急行": (0, "commuter", False, "measured", WIKI + "京阪本線"),
    "京阪電気鉄道|本線|快速急行": (0, "commuter", False, "measured", WIKI + "京阪本線"),
    "京阪電気鉄道|本線|区間急行": (0, "commuter", False, "measured", WIKI + "京阪本線"),
    # 南海高野線 日中: 「快速急行・急行 2本」= 両者合わせて2本。停車駅がほぼ同じなので
    # 急行に2本を集約し、快速急行は二重計上を避けるため除外する
    "南海電気鉄道|高野線|急行": (2, "commuter", False, "measured", WIKI + "南海高野線"),
    "南海電気鉄道|高野線|快速急行": (0, "commuter", False, "measured", WIKI + "南海高野線"),
    "南海電気鉄道|高野線|区間急行": (2, "commuter", False, "inferred", WIKI + "南海高野線"),
    "南海電気鉄道|高野線|準急行": (2, "commuter", False, "measured", WIKI + "南海高野線"),
    "南海電気鉄道|高野線|ＧＲＡＮ天空": (0, "tourist", True, "measured", WIKI + "南海高野線"),
    # 近鉄南大阪線 日中: 区間急行2本 / 準急2本+長野線直通4本 / 普通6本。急行は日中を除く時間帯
    "近畿日本鉄道|南大阪線|急行": (0, "commuter", False, "measured", WIKI + "近鉄南大阪線"),
    "近畿日本鉄道|南大阪線|区間急行": (2, "commuter", False, "measured", WIKI + "近鉄南大阪線"),
    "近畿日本鉄道|南大阪線|準急": (6, "commuter", False, "measured", WIKI + "近鉄南大阪線"),
    # 近鉄大阪線 日中: 急行3本 / 区間準急4本。快速急行は昼間時以外
    "近畿日本鉄道|大阪線|急行": (3, "commuter", False, "measured", WIKI + "近鉄大阪線"),
    "近畿日本鉄道|大阪線|区間準急": (4, "commuter", False, "measured", WIKI + "近鉄大阪線"),
    "近畿日本鉄道|大阪線|快速急行": (0, "commuter", False, "measured", WIKI + "近鉄大阪線"),
    "近畿日本鉄道|大阪線|区間急行": (0, "commuter", False, "inferred", WIKI + "近鉄大阪線"),
    "近畿日本鉄道|大阪線|準急": (0, "commuter", False, "inferred", WIKI + "近鉄大阪線"),
    # 近鉄奈良線 日中: 快速急行3 / 急行3 / 区間準急3 / 普通3。準急は朝夕のみ
    "近畿日本鉄道|奈良線|急行": (3, "commuter", False, "measured", WIKI + "近鉄奈良線"),
    "近畿日本鉄道|奈良線|区間準急": (3, "commuter", False, "measured", WIKI + "近鉄奈良線"),
    "近畿日本鉄道|奈良線|準急": (0, "commuter", False, "measured", WIKI + "近鉄奈良線"),
    # 阪急宝塚本線 日中: 急行6本 / 普通6本。特急(日生エクスプレス)は朝夕のみ
    "阪急電鉄|宝塚本線|急行": (6, "commuter", False, "measured", WIKI + "阪急宝塚本線"),
    "阪急電鉄|宝塚本線|特急": (0, "commuter", False, "measured", WIKI + "阪急宝塚本線"),
    # 阪神本線 平日日中: 直通特急2 / 特急2 / 快速急行3 / 急行3 / 普通6
    "阪神電気鉄道|本線|特急": (2, "commuter", False, "measured", WIKI + "阪神本線"),
    "阪神電気鉄道|本線|直通特急": (2, "commuter", False, "measured", WIKI + "阪神本線"),
    "阪神電気鉄道|本線|急行": (3, "commuter", False, "measured", WIKI + "阪神本線"),

    # ---------------------------------------------------------------- その他
    "大阪モノレール|本線|普通": (6, "commuter", False, "measured", WIKI + "大阪モノレール線"),
    "大阪モノレール|国際文化公園都市モノレール線|普通": (4, "commuter", False, "inferred", WIKI + "大阪モノレール彩都線"),
    "能勢電鉄|妙見線|普通": (6, "commuter", False, "measured", WIKI + "能勢電鉄妙見線"),
    "水間鉄道|水間鉄道|普通": (2, "commuter", False, "measured", WIKI + "水間鉄道水間線"),
    # 阪堺は同じ事業者でも区間で頻度が全く違うので、阪堺線を住吉で二分してある
    # （build_graph.SERVICE_SPLITS）。
    #  - 上町線(天王寺駅前〜住吉): 天王寺駅前〜浜寺駅前 と 天王寺駅前〜我孫子道 の2系統が
    #    それぞれ12分間隔 → 合わせて6分間隔
    #  - 阪堺線(恵美須町〜住吉): 恵美須町発着は全て我孫子道止まり、昼間 平日28分間隔のみ
    #  - 阪堺線(住吉〜浜寺駅前): 上町線からの天王寺駅前〜浜寺駅前系統が12分間隔で流入
    "阪堺電気軌道|上町線|普通": (10, "commuter", False, "measured", WIKI + "阪堺電気軌道上町線"),
    "阪堺電気軌道|阪堺線(住吉〜恵美須町)|普通": (2.1, "commuter", False, "measured",
                                       WIKI + "阪堺電気軌道阪堺線"),
    "阪堺電気軌道|阪堺線(住吉〜浜寺駅前)|普通": (5, "commuter", False, "measured",
                                      WIKI + "阪堺電気軌道上町線"),
}

# 新幹線は種別で一括除外（府内の停車駅は新大阪のみ。居住可達性には効かない）
EXCLUDE_CLASSES = {"新幹線"}


def classify(line_key, service_class):
    """(layer, headway, role, fare_extra, conf, src, reason) を返す。"""
    if service_class in EXCLUDE_CLASSES:
        return ("excluded", None, "shinkansen", True, "measured", "",
                "新幹線。府内の停車駅は新大阪のみで居住可達性に寄与しない")
    row = LEVELS.get(f"{line_key}|{service_class}")
    if row is None:
        return ("unclassified", None, None, None, None, "", "分級表に未登録")
    hw, role, fare, conf, src = row
    if role in ("tourist", "seasonal"):
        return ("excluded", hw, role, fare, conf, src, "観光/季節列車のため両層とも辺を張らない")
    if hw == 0:
        return ("excluded", hw, role, fare, conf, src,
                "日中(10-16時)に運行がない（朝夕のみ）。日中モデルの対象外")
    if hw >= 3:
        return ("A", hw, role, fare, conf, src, f"日中{hw}本/h ≥ 3本/h")
    return ("B", hw, role, fare, conf, src,
            f"日中{hw}本/h < 3本/h だが{role}機能を担うため低頻度層へ")

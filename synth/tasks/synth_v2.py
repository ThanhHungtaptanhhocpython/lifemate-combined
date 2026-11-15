"""Tasks v2: purchase cart->checkout vs cart-only, list/holdings before code lookup, empty-query date/name lookup, calibrated ASK."""
from _common import ASK, C, CALENDAR, CONTACTS, SMS, T

NOW = "2026-11-12T09:00:00+07:00"   # Thursday
EVE = "2026-11-12T19:30:00+07:00"
MON = "2026-11-16T10:00:00+07:00"   # Monday

GIFT = {
    "default_address": "25 Láng Hạ, Đống Đa, Hà Nội",
    "products": [
        {"id": "gp_01", "name": "Bình giữ nhiệt Lock&Lock 500ml", "category": "đồ gia dụng", "price": 290000},
        {"id": "gp_02", "name": "Đèn ngủ để bàn ánh vàng ấm", "category": "trang trí", "price": 350000},
        {"id": "gp_03", "name": "Sổ tay bìa da cao cấp A5", "category": "văn phòng phẩm", "price": 180000},
        {"id": "gp_04", "name": "Hộp trà sen Hồ Tây biếu tặng", "category": "quà biếu", "price": 450000},
    ],
    "cart": [],
    "orders": [
        {"id": "gm_01", "items": [{"product_id": "gp_03", "quantity": 1}], "total": 180000, "payment_method": "cod",
         "address": "25 Láng Hạ, Đống Đa, Hà Nội", "status": "placed"},
    ],
}

GIFT_EXISTING_CART = {
    **GIFT,
    "cart": [{"product_id": "gp_02", "name": "Đèn ngủ để bàn ánh vàng ấm", "price": 350000, "quantity": 2}],
}

BAKERY = {
    "items": [
        {"id": "bk_01", "name": "Bánh mì hoa cúc Pháp", "tag": "bánh mì", "price": 65000},
        {"id": "bk_02", "name": "Bánh tiramisu hộp 250g", "tag": "bánh ngọt", "price": 140000},
        {"id": "bk_03", "name": "Trà sữa ô long kem cheese", "tag": "đồ uống", "price": 55000},
        {"id": "bk_04", "name": "Bánh su kem nhân vani hộp 6 cái", "tag": "bánh ngọt", "price": 90000},
    ],
    "cart": [],
    "orders": [],
}

MARKET = {
    "holdings": [
        {"code": "QDVN", "name": "Quỹ Đầu Tư Việt Nam", "quantity": 500, "price": 24500},
        {"code": "ANBINH", "name": "CTCP Công Nghệ An Bình", "quantity": 200, "price": 62000},
    ],
    "instruments": [
        {"code": "QDVN", "name": "Quỹ Đầu Tư Việt Nam", "price": 24500},
        {"code": "ANBINH", "name": "CTCP Công Nghệ An Bình", "price": 62000},
        {"code": "KIMN", "name": "Quỹ Trái Phiếu Kim Ngân", "price": 18200},
        {"code": "XANHVN", "name": "CTCP Năng Lượng Xanh", "price": 41000},
    ],
    "orders": [],
    "alerts": [],
}

WORKSHOP = {
    "events": [
        {"id": "ev_01", "name": "Hội thảo AI Ứng Dụng Thực Chiến", "topic": "công nghệ", "date": "2026-11-17", "time": "19:00", "price": 150000, "available": 30},
        {"id": "ev_02", "name": "Đêm nhạc Acoustic Mùa Thu", "topic": "âm nhạc", "date": "2026-11-21", "time": "20:00", "price": 300000, "available": 15},
        {"id": "ev_03", "name": "Workshop Làm Gốm Cuối Tuần", "topic": "thủ công", "date": "2026-11-22", "time": "09:30", "price": 250000, "available": 12},
        {"id": "ev_04", "name": "Stand-up Comedy Chuyện Công Sở", "topic": "hài kịch", "date": "2026-11-24", "time": "20:00", "price": 200000, "available": 20},
    ],
    "passes": [
        {"id": "wp_01", "event_id": "ev_02", "quantity": 2, "total": 600000, "status": "booked"},
    ],
}

WALLET_RICH = {"balance": 1500000, "transactions": []}
WALLET_LOW = {"balance": 100000, "transactions": []}
BANK = {"accounts": [{"id": "acc_01", "bank": "VCB", "balance": 5000000}], "transactions": []}

GM = {"gift_mart": GIFT}
GMC = {"gift_mart": GIFT_EXISTING_CART}
GMW = {"gift_mart": GIFT, "ewallet": WALLET_LOW, "banking": BANK}
GMR = {"gift_mart": GIFT, "ewallet": WALLET_RICH, "banking": BANK}
BK = {"bakery_shop": BAKERY}
BKW = {"bakery_shop": BAKERY, "ewallet": WALLET_RICH}
MK = {"market_watch": MARKET}
WS = {"workshop_pass": WORKSHOP}
WSC = {"workshop_pass": WORKSHOP, "calendar": CALENDAR}

TASKS = [
    # --- gift_mart: cart -> checkout vs cart-only ---
    T("gm_buy_cod", NOW, "Đặt mua giúp em một cái bình giữ nhiệt Lock&Lock, thanh toán khi nhận hàng nhé.",
      [C("gift_mart.search_products", query="bình giữ nhiệt"), C("gift_mart.add_to_cart", product_id="gp_01", quantity=1),
       C("gift_mart.checkout", payment_method="cod")], GM),
    T("gm_buy_wallet_addr", NOW, "Mua cho chị hai hộp trà sen Hồ Tây giao về 88 Nguyễn Du, trả bằng ví.",
      [C("gift_mart.search_products", query="trà sen"), C("gift_mart.add_to_cart", product_id="gp_04", quantity=2),
       C("gift_mart.checkout", payment_method="wallet", address="88 Nguyễn Du")], GM),
    T("gm_buy_multi", EVE, "Đặt đơn một cái đèn ngủ ánh vàng với hai cuốn sổ tay bìa da, chuyển khoản ngân hàng.",
      [C("gift_mart.search_products", query="đèn ngủ"), C("gift_mart.add_to_cart", product_id="gp_02", quantity=1),
       C("gift_mart.search_products", query="sổ tay"), C("gift_mart.add_to_cart", product_id="gp_03", quantity=2),
       C("gift_mart.checkout", payment_method="bank")], GM),
    T("gm_cart_only_1", NOW, "Tìm bình giữ nhiệt Lock&Lock rồi bỏ tạm một cái vào giỏ hàng giúp anh.",
      [C("gift_mart.search_products", query="bình giữ nhiệt"), C("gift_mart.add_to_cart", product_id="gp_01", quantity=1)], GM),
    T("gm_cart_only_2", NOW, "Thêm hai chiếc đèn ngủ ánh vàng vào giỏ thôi nhé, chưa cần thanh toán đâu.",
      [C("gift_mart.search_products", query="đèn ngủ"), C("gift_mart.add_to_cart", product_id="gp_02", quantity=2)], GM),
    T("gm_checkout_existing", NOW, "Thanh toán giỏ hàng quà tặng đang có bằng tiền mặt khi nhận hàng đi em.",
      [C("gift_mart.get_cart"), C("gift_mart.checkout", payment_method="cod")], GMC),
    T("gm_cond_wallet_low", NOW, "Mua một cái đèn ngủ ánh vàng ấm, trả bằng ví nếu ví đủ tiền, không thì thanh toán ngân hàng.",
      [C("gift_mart.search_products", query="đèn ngủ"), C("ewallet.get_balance"),
       C("gift_mart.add_to_cart", product_id="gp_02", quantity=1), C("gift_mart.checkout", payment_method="bank")], GMW),
    T("gm_cond_wallet_rich", NOW, "Đặt một hộp trà sen Hồ Tây, nếu ví đủ thì trả ví, thiếu thì trả ngân hàng.",
      [C("gift_mart.search_products", query="trà sen"), C("ewallet.get_balance"),
       C("gift_mart.add_to_cart", product_id="gp_04", quantity=1), C("gift_mart.checkout", payment_method="wallet")], GMR),
    T("gm_list_all_empty_query", NOW, "Xem cửa hàng quà tặng đang có những gì dưới ba trăm nghìn rồi mua giúp anh một cuốn sổ tay bằng ví.",
      [C("gift_mart.search_products", query="", max_price=300000), C("gift_mart.add_to_cart", product_id="gp_03", quantity=1),
       C("gift_mart.checkout", payment_method="wallet")], GM),
    T("gm_cancel_order", NOW, "Huỷ giúp chị đơn quà tặng sổ tay đã đặt hôm trước đi.",
      [C("gift_mart.order_status"), C("gift_mart.cancel_order", order_id="gm_01")], GM),
    T("gm_missing_payment", NOW, "Đặt mua cho anh một hộp trà sen Hồ Tây giao về nhà.",
      [C("gift_mart.search_products", query="trà sen"), C("gift_mart.add_to_cart", product_id="gp_04", quantity=1),
       ASK("gift_mart.checkout", "payment_method")], GM),
    T("gm_missing_product", NOW, "Mua giúp chị một món đồ trang trí bàn học tầm hai trăm nghìn nhé.",
      [C("gift_mart.search_products", query=""), ASK("gift_mart.add_to_cart", "product_id")], GM),

    # --- bakery_shop: cart -> checkout vs cart-only + multi-item ---
    T("bk_buy_cod", NOW, "Đặt giao ngay hai ổ bánh mì hoa cúc và hai ly trà sữa ô long, trả tiền mặt khi nhận.",
      [C("bakery_shop.search_menu", query="bánh mì hoa cúc"), C("bakery_shop.add_to_cart", item_id="bk_01", quantity=2),
       C("bakery_shop.search_menu", query="trà sữa ô long"), C("bakery_shop.add_to_cart", item_id="bk_03", quantity=2),
       C("bakery_shop.checkout", payment_method="cod")], BK),
    T("bk_buy_scheduled", NOW, "Mua một hộp bánh tiramisu thanh toán bằng ví, giao lúc bốn giờ chiều nay.",
      [C("bakery_shop.search_menu", query="tiramisu"), C("bakery_shop.add_to_cart", item_id="bk_02", quantity=1),
       C("bakery_shop.checkout", payment_method="wallet", delivery_time="2026-11-12T16:00:00+07:00")], BKW),
    T("bk_cart_only", NOW, "Bỏ ba hộp bánh su kem nhân vani vào giỏ tiệm bánh giúp mình trước đã.",
      [C("bakery_shop.search_menu", query="su kem"), C("bakery_shop.add_to_cart", item_id="bk_04", quantity=3)], BK),
    T("bk_list_menu_buy", NOW, "Cho xem thực đơn tiệm bánh có món gì rồi đặt luôn một hộp tiramisu trả ngân hàng.",
      [C("bakery_shop.search_menu", query=""), C("bakery_shop.add_to_cart", item_id="bk_02", quantity=1),
       C("bakery_shop.checkout", payment_method="bank")], BK),
    T("bk_missing_qty", NOW, "Đặt bánh su kem nhân vani, thanh toán tiền mặt giúp em.",
      [C("bakery_shop.search_menu", query="su kem"), ASK("bakery_shop.add_to_cart", "quantity")], BK),

    # --- market_watch: read holdings/instruments FIRST, never guess code! ---
    T("mk_quote_by_name_held", NOW, "Kiểm tra giúp anh giá hiện tại của Quỹ Đầu Tư Việt Nam xem bao nhiêu.",
      [C("market_watch.get_holdings"), C("market_watch.get_price", code="QDVN")], MK),
    T("mk_quote_by_name_all", NOW, "Xem giá cổ phần Năng Lượng Xanh hôm nay thế nào em.",
      [C("market_watch.list_instruments"), C("market_watch.get_price", code="XANHVN")], MK),
    T("mk_buy_lookup", NOW, "Đặt mua ba trăm đơn vị Quỹ Trái Phiếu Kim Ngân ở giá mười tám nghìn hai trăm.",
      [C("market_watch.list_instruments"), C("market_watch.submit_order", code="KIMN", side="buy", quantity=300, price=18200)], MK),
    T("mk_sell_cond_ok", NOW, "Nếu đang giữ ít nhất một trăm cổ phần Công Nghệ An Bình thì đặt bán một trăm ở giá sáu mươi ba nghìn.",
      [C("market_watch.get_holdings"), C("market_watch.submit_order", code="ANBINH", side="sell", quantity=100, price=63000)], MK),
    T("mk_sell_cond_skip", NOW, "Nếu đang nắm trên sáu trăm đơn vị Quỹ Đầu Tư Việt Nam thì bán bớt hai trăm giá hai mươi lăm nghìn.",
      [C("market_watch.get_holdings")], MK),
    T("mk_alert_lookup", NOW, "Đặt cảnh báo khi Công Nghệ An Bình vượt lên trên sáu mươi lăm nghìn nhé.",
      [C("market_watch.get_holdings"), C("market_watch.set_alert", code="ANBINH", price=65000, direction="above")], MK),
    T("mk_missing_price", NOW, "Đặt mua hai trăm cổ phần Năng Lượng Xanh giúp anh.",
      [C("market_watch.list_instruments"), ASK("market_watch.submit_order", "price")], MK),
    T("mk_missing_code", NOW, "Bán một nửa số cổ phần đang giữ ở giá hiện tại đi em.",
      [C("market_watch.get_holdings"), ASK("market_watch.submit_order", "code")], MK),

    # --- workshop_pass: date-only / noisy-name -> search_events(query="") ---
    T("ws_date_next_tue", NOW, "Tìm giúp mình hội thảo diễn ra vào thứ ba tuần sau rồi đặt một vé nhé.",
      [C("workshop_pass.search_events", query=""), C("workshop_pass.reserve_pass", event_id="ev_01", quantity=1)], WS),
    T("ws_date_weekend_cal", NOW, "Chủ nhật tuần sau có workshop gì hay không, đặt hai vé và ghi vào lịch giúp chị.",
      [C("workshop_pass.search_events", query=""), C("workshop_pass.reserve_pass", event_id="ev_03", quantity=2),
       C("calendar.create_event", title="Workshop Làm Gốm Cuối Tuần", start="2026-11-22T09:30:00+07:00", end="2026-11-22T11:30:00+07:00")], WSC),
    T("ws_topic_comedy", MON, "Kiểm tra có show hài kịch nào không rồi đặt hai vé cho anh.",
      [C("workshop_pass.search_events", query=""), C("workshop_pass.reserve_pass", event_id="ev_04", quantity=2)], WS),
    T("ws_cancel", NOW, "Huỷ vé đêm nhạc Acoustic Mùa Thu chị đã đặt đi em.",
      [C("workshop_pass.my_passes"), C("workshop_pass.cancel_pass", pass_id="wp_01")], WS),
    T("ws_missing_qty", NOW, "Đặt giúp mình vé tham gia hội thảo AI Ứng Dụng Thực Chiến nhé.",
      [C("workshop_pass.search_events", query="AI"), ASK("workshop_pass.reserve_pass", "quantity")], WS),
]

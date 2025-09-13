import requests
import websocket
import json
import pandas as pd
import time
import threading

# 全局订单簿存储（使用字典，键为价格，值为数量）
order_book = {"bids": {}, "asks": {}}
last_update_id = 0  # 记录最后处理的更新ID

# 添加全局变量来跟踪订单变化
order_changes = {"bids": {}, "asks": {}}
# 添加变量来跟踪已移除的订单
removed_orders = {"bids": {}, "asks": {}}

# Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1350837714601377792/Gdmxej07wvWgJXxQ3qSqV8o-7Oaw5xc1kHGDw1K3sgXfrVuk6PsiUHymvVn-fU4GeMsd"
DISCORD_WEBHOOK_URL2 = "https://discordapp.com/api/webhooks/1367897839916683365/T9FOLGaqf1Hg-LEblt_WcMUfk__ZGwxjWzjlrd2tlHLEruJGTSFzvv8f5iHw-HW8Y29z"

# 上次发送到Discord的时间
last_discord_send_time = 0
# Discord发送间隔（5分钟）
DISCORD_SEND_INTERVAL = 300  # 秒

def send_to_discord(content):
    """发送消息到Discord Webhook"""
    data = {
        "content": content
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response2 = requests.post(DISCORD_WEBHOOK_URL2, json=data)
        if response.status_code == 204 or response2.status_code == 204:
            print("消息已成功发送到Discord")
        else:
            print(f"发送到Discord失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"发送到Discord时出错: {e}")

def get_initial_snapshot(symbol="BTCUSDT", limit=5000):
    """获取初始订单簿快照"""
    url = "https://api.binance.com/api/v3/depth"
    params = {"symbol": symbol, "limit": limit}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception(f"REST API请求失败，状态码: {response.status_code}")
    
    data = response.json()
    global last_update_id
    last_update_id = data["lastUpdateId"]
    
    # 初始化订单簿
    for price, qty in data["bids"]:
        order_book["bids"][float(price)] = float(qty)
    for price, qty in data["asks"]:
        order_book["asks"][float(price)] = float(qty)
    
    print(f"初始快照加载完成，lastUpdateId: {last_update_id}")
    print_order_book_summary()

def apply_update(bids_updates, asks_updates):
    """应用增量更新到订单簿"""
    global last_update_id, order_changes, removed_orders
    
    # 更新买入订单
    for price, qty in bids_updates:
        price = float(price)
        qty = float(qty)
        old_qty = order_book["bids"].get(price, 0)
        change = qty - old_qty
        
        if qty == 0:
            order_book["bids"].pop(price, None)  # 删除数量为0的订单
            if old_qty > 50:  # 只记录大于50的变化
                order_changes["bids"][price] = -old_qty  # 记录为完全移除
                removed_orders["bids"][price] = old_qty  # 记录被移除的订单
        else:
            order_book["bids"][price] = qty      # 更新或添加订单
            if abs(change) > 50:  # 只记录大于50的变化
                order_changes["bids"][price] = change
    
    # 更新卖出订单
    for price, qty in asks_updates:
        price = float(price)
        qty = float(qty)
        old_qty = order_book["asks"].get(price, 0)
        change = qty - old_qty
        
        if qty == 0:
            order_book["asks"].pop(price, None)
            if old_qty > 50:  # 只记录大于50的变化
                order_changes["asks"][price] = -old_qty  # 记录为完全移除
                removed_orders["asks"][price] = old_qty  # 记录被移除的订单
        else:
            order_book["asks"][price] = qty
            if abs(change) > 50:  # 只记录大于50的变化
                order_changes["asks"][price] = change

def calculate_depth_ratio(price_range_percent=1.0):
    """计算距离当前价格一定百分比范围内的买卖比率"""
    if not order_book["bids"] or not order_book["asks"]:
        return None, 0, 0, 0
    
    # 获取当前中间价格
    highest_bid = max(order_book["bids"].keys())
    lowest_ask = min(order_book["asks"].keys())
    mid_price = (highest_bid + lowest_ask) / 2
    
    # 计算价格范围
    lower_bound = mid_price * (1 - price_range_percent / 100)
    upper_bound = mid_price * (1 + price_range_percent / 100)
    
    # 计算范围内的买单总量
    bids_in_range = {price: qty for price, qty in order_book["bids"].items() if price >= lower_bound}
    bids_volume = sum(bids_in_range.values())
    
    # 计算范围内的卖单总量
    asks_in_range = {price: qty for price, qty in order_book["asks"].items() if price <= upper_bound}
    asks_volume = sum(asks_in_range.values())
    
    # 计算买卖差值
    delta = bids_volume - asks_volume
    
    # 计算买卖总量
    total = bids_volume + asks_volume
    
    # 计算比率 (delta/total)
    ratio = delta / total if total > 0 else 0
    
    return ratio, bids_volume, asks_volume, delta

def calculate_depth_ratio_range(lower_percent, upper_percent):
    """计算指定价格范围内的买卖比率"""
    if not order_book["bids"] or not order_book["asks"]:
        return None, 0, 0, 0
    
    # 获取当前中间价格
    highest_bid = max(order_book["bids"].keys())
    lowest_ask = min(order_book["asks"].keys())
    mid_price = (highest_bid + lowest_ask) / 2
    
    # 计算价格范围
    lower_bound = mid_price * (1 - upper_percent / 100)
    upper_bound = mid_price * (1 + upper_percent / 100)
    inner_lower_bound = mid_price * (1 - lower_percent / 100)
    inner_upper_bound = mid_price * (1 + lower_percent / 100)
    
    # 计算范围内的买单总量 (只计算在指定范围内的订单)
    bids_in_range = {price: qty for price, qty in order_book["bids"].items() 
                    if price >= lower_bound and price < inner_lower_bound}
    bids_volume = sum(bids_in_range.values())
    
    # 计算范围内的卖单总量
    asks_in_range = {price: qty for price, qty in order_book["asks"].items() 
                    if price <= upper_bound and price > inner_upper_bound}
    asks_volume = sum(asks_in_range.values())
    
    # 计算买卖差值
    delta = bids_volume - asks_volume
    
    # 计算买卖总量
    total = bids_volume + asks_volume
    
    # 计算比率 (delta/total)
    ratio = delta / total if total > 0 else 0
    
    return ratio, bids_volume, asks_volume, delta

def generate_market_analysis():
    """生成市场分析文本，用于发送到Discord"""
    global order_changes, removed_orders
    
    if not order_book["bids"] or not order_book["asks"]:
        return "订单簿数据不足，无法分析"
    
    highest_bid = max(order_book["bids"].keys())
    lowest_ask = min(order_book["asks"].keys())
    mid_price = (highest_bid + lowest_ask) / 2
    spread = lowest_ask - highest_bid # 计算价差

    # 添加订单簿摘要信息
    min_quantity = 50.0
    limit = 10  # 限制显示的订单数量
    
    # 转换为DataFrame
    bids_df = pd.DataFrame(list(order_book["bids"].items()), columns=["price", "quantity"])
    asks_df = pd.DataFrame(list(order_book["asks"].items()), columns=["price", "quantity"])
    
    # 过滤数量大于50 BTC的订单
    bids_df_display = bids_df[bids_df["quantity"] > min_quantity].sort_values(by="price", ascending=False)
    asks_df_display = asks_df[asks_df["quantity"] > min_quantity].sort_values(by="price", ascending=True)
    
    # 限制显示条数
    bids_df_display = bids_df_display.head(limit)
    asks_df_display = asks_df_display.head(limit)
    
    # 构建订单簿摘要文本
    order_book_summary = f"**BTC/USDT 订单簿摘要** (数量 > {min_quantity} BTC，前{limit}条):\n\n"
    
    # 添加卖出订单信息
    order_book_summary += "**卖出订单 (Asks):**\n"
    if asks_df_display.empty:
        order_book_summary += "无符合条件的卖出订单\n"
    else:
        # 卖单按价格从高到低排序显示
        asks_sorted = asks_df_display.sort_values(by="price", ascending=False)
        for _, row in asks_sorted.iterrows():
            price = row['price']
            change_str = ""
            if price in order_changes["asks"]:
                change = order_changes["asks"][price]
                sign = "+" if change > 0 else ""
                change_str = f" ({sign}{change:.4f})"
            order_book_summary += f"价格: ${price:.2f}, 数量: {row['quantity']:.4f} BTC{change_str}\n"
    
    # 添加已移除的卖单信息
    if removed_orders["asks"]:
        order_book_summary += "\n**已移除的卖单:**\n"
        for price, qty in sorted(removed_orders["asks"].items(), reverse=True):
            order_book_summary += f"价格: ${price:.2f}, 原数量: {qty:.4f} BTC (已完全移除)\n"
    
    # 添加买入订单信息
    order_book_summary += "\n**买入订单 (Bids):**\n"
    if bids_df_display.empty:
        order_book_summary += "无符合条件的买入订单\n"
    else:
        for _, row in bids_df_display.iterrows():
            price = row['price']
            change_str = ""
            if price in order_changes["bids"]:
                change = order_changes["bids"][price]
                sign = "+" if change > 0 else ""
                change_str = f" ({sign}{change:.4f})"
            order_book_summary += f"价格: ${price:.2f}, 数量: {row['quantity']:.4f} BTC{change_str}\n"
    
    # 添加已移除的买单信息
    if removed_orders["bids"]:
        order_book_summary += "\n**已移除的买单:**\n"
        for price, qty in sorted(removed_orders["bids"].items(), reverse=False):
            order_book_summary += f"价格: ${price:.2f}, 原数量: {qty:.4f} BTC (已完全移除)\n"
    
    # 计算各个范围的买卖比率
    ratio, bids_vol, asks_vol, delta = calculate_depth_ratio(1.0)
    ratio_1_25, bids_vol_1_25, asks_vol_1_25, delta_1_25 = calculate_depth_ratio_range(1.0, 2.5)
    ratio_25_5, bids_vol_25_5, asks_vol_25_5, delta_25_5 = calculate_depth_ratio_range(2.5, 5.0)
    ratio_5_10, bids_vol_5_10, asks_vol_5_10, delta_5_10 = calculate_depth_ratio_range(5.0, 10.0)
    
    # 生成分析结论
    analysis = ""
    if ratio > 0.1 and ratio_1_25 > 0 and ratio_25_5 > 0:
        analysis = "近期买方力量强劲，多层次支撑，强烈看涨"
    elif ratio < -0.1 and ratio_1_25 < 0 and ratio_25_5 < 0:
        analysis = "近期卖方力量强劲，多层次压力，强烈看跌"
    elif ratio > 0 and ratio_1_25 > 0:
        analysis = "短期内买方略占优势，可能上涨"
    elif ratio < 0 and ratio_1_25 < 0:
        analysis = "短期内卖方略占优势，可能下跌"
    else:
        analysis = "买卖力量较为平衡，价格可能在区间内波动"
    
    # 构建完整消息
    message = f"==================================================================\n\n"
    message += f"**币安 BTC/USDT 市场深度分析** - {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    message += f"当前价格: ${highest_bid:.2f} (最高买价) / ${lowest_ask:.2f} (最低卖价) / ${mid_price:.2f} (中间价)\n"
    message += f"当前价差: ${spread:.2f}\n\n" # 添加价差显示
    message += order_book_summary + "\n"  # 添加订单簿摘要
    message += f"0-1%价格范围内买卖比率: {ratio:.4f}\n"
    message += f"买量: {bids_vol:.4f} BTC, 卖量: {asks_vol:.4f} BTC, 差值: {delta:.4f} BTC\n\n"
    message += f"1-2.5%价格范围内买卖比率: {ratio_1_25:.4f}\n"
    message += f"买量: {bids_vol_1_25:.4f} BTC, 卖量: {asks_vol_1_25:.4f} BTC, 差值: {delta_1_25:.4f} BTC\n\n"
    message += f"2.5-5%价格范围内买卖比率: {ratio_25_5:.4f}\n"
    message += f"买量: {bids_vol_25_5:.4f} BTC, 卖量: {asks_vol_25_5:.4f} BTC, 差值: {delta_25_5:.4f} BTC\n\n"
    message += f"5-10%价格范围内买卖比率: {ratio_5_10:.4f}\n"
    message += f"买量: {bids_vol_5_10:.4f} BTC, 卖量: {asks_vol_5_10:.4f} BTC, 差值: {delta_5_10:.4f} BTC\n\n"
    #message += f"**市场深度分析结论:**\n{analysis}"
    
    return message

# Modify print_order_book_summary to include Discord sending logic
def print_order_book_summary(limit=10, min_quantity=50.0):
    """打印订单簿摘要，仅显示数量大于50 BTC的订单，但计算比率时使用所有订单"""
    global last_discord_send_time, order_changes, removed_orders
    current_time = time.time()
    
    # 转换为DataFrame
    bids_df = pd.DataFrame(list(order_book["bids"].items()), columns=["price", "quantity"])
    asks_df = pd.DataFrame(list(order_book["asks"].items()), columns=["price", "quantity"])
    
    # 过滤数量大于50 BTC的订单（仅用于显示）
    bids_df_display = bids_df[bids_df["quantity"] > min_quantity].sort_values(by="price", ascending=False)
    asks_df_display = asks_df[asks_df["quantity"] > min_quantity].sort_values(by="price", ascending=True)
    
    # 限制显示条数
    bids_df_display = bids_df_display.head(limit)
    asks_df_display = asks_df_display.head(limit)
    
    print(f"\n币安 BTC/USDT 订单簿摘要 (数量 > {min_quantity} BTC，前{limit}条):")
    
    # 先显示卖出订单（上方）
    print("\n卖出订单 (Asks):")
    if asks_df_display.empty:
        print("无符合条件的卖出订单")
    else:
        # 卖单按价格从高到低排序显示（从上到下）
        asks_sorted = asks_df_display.sort_values(by="price", ascending=False)
        for _, row in asks_sorted.iterrows():
            price = row['price']
            change_str = ""
            if price in order_changes["asks"]:
                change = order_changes["asks"][price]
                sign = "+" if change > 0 else ""
                change_str = f" ({sign}{change:.4f})"
            print(f"价格: ${price:.2f}, 数量: {row['quantity']:.4f} BTC{change_str}")
    
    # 显示已移除的卖单
    if removed_orders["asks"]:
        print("\n已移除的卖单:")
        for price, qty in sorted(removed_orders["asks"].items(), reverse=True):
            print(f"价格: ${price:.2f}, 原数量: {qty:.4f} BTC (已完全移除)")
    
    # 再显示买入订单（下方）
    print("\n买入订单 (Bids):")
    if bids_df_display.empty:
        print("无符合条件的买入订单")
    else:
        for _, row in bids_df_display.iterrows():
            price = row['price']
            change_str = ""
            if price in order_changes["bids"]:
                change = order_changes["bids"][price]
                sign = "+" if change > 0 else ""
                change_str = f" ({sign}{change:.4f})"
            print(f"价格: ${price:.2f}, 数量: {row['quantity']:.4f} BTC{change_str}")
    
    # 显示已移除的买单
    if removed_orders["bids"]:
        print("\n已移除的买单:")
        for price, qty in sorted(removed_orders["bids"].items(), reverse=False):
            print(f"价格: ${price:.2f}, 原数量: {qty:.4f} BTC (已完全移除)")
    
    # 计算并显示当前价格 (使用所有订单计算)
    if not bids_df.empty and not asks_df.empty:
        highest_bid = max(order_book["bids"].keys())
        lowest_ask = min(order_book["asks"].keys())
        mid_price = (highest_bid + lowest_ask) / 2
        print(f"\n当前价格: ${highest_bid:.2f} (最高买价) / ${lowest_ask:.2f} (最低卖价) / ${mid_price:.2f} (中间价)")
        
        # 计算并显示0-1%范围内的买卖比率 (使用所有订单计算)
        ratio, bids_vol, asks_vol, delta = calculate_depth_ratio(1.0)
        if ratio is not None:
            print(f"\n0-1%价格范围内买卖比率: {ratio:.4f}")
            print(f"买量: {bids_vol:.4f} BTC, 卖量: {asks_vol:.4f} BTC, 差值: {delta:.4f} BTC")
            
            # 计算并显示1-2.5%范围内的买卖比率
            ratio_1_25, bids_vol_1_25, asks_vol_1_25, delta_1_25 = calculate_depth_ratio_range(1.0, 2.5)
            print(f"\n1-2.5%价格范围内买卖比率: {ratio_1_25:.4f}")
            print(f"买量: {bids_vol_1_25:.4f} BTC, 卖量: {asks_vol_1_25:.4f} BTC, 差值: {delta_1_25:.4f} BTC")
            
            # 计算并显示2.5-5%范围内的买卖比率
            ratio_25_5, bids_vol_25_5, asks_vol_25_5, delta_25_5 = calculate_depth_ratio_range(2.5, 5.0)
            print(f"\n2.5-5%价格范围内买卖比率: {ratio_25_5:.4f}")
            print(f"买量: {bids_vol_25_5:.4f} BTC, 卖量: {asks_vol_25_5:.4f} BTC, 差值: {delta_25_5:.4f} BTC")
            
            # 计算并显示5-10%范围内的买卖比率
            ratio_5_10, bids_vol_5_10, asks_vol_5_10, delta_5_10 = calculate_depth_ratio_range(5.0, 10.0)
            print(f"\n5-10%价格范围内买卖比率: {ratio_5_10:.4f}")
            print(f"买量: {bids_vol_5_10:.4f} BTC, 卖量: {asks_vol_5_10:.4f} BTC, 差值: {delta_5_10:.4f} BTC")
            
            # 综合分析
            print("\n市场深度分析:")
            if ratio > 0.1 and ratio_1_25 > 0 and ratio_25_5 > 0:
                print("近期买方力量强劲，多层次支撑，强烈看涨")
            elif ratio < -0.1 and ratio_1_25 < 0 and ratio_25_5 < 0:
                print("近期卖方力量强劲，多层次压力，强烈看跌")
            elif ratio > 0 and ratio_1_25 > 0:
                print("短期内买方略占优势，可能上涨")
            elif ratio < 0 and ratio_1_25 < 0:
                print("短期内卖方略占优势，可能下跌")
            else:
                print("买卖力量较为平衡，价格可能在区间内波动")
            
            # 检查是否需要发送到Discord
            if current_time - last_discord_send_time >= DISCORD_SEND_INTERVAL:
                discord_message = generate_market_analysis()
                send_to_discord(discord_message)
                last_discord_send_time = current_time
                print(f"\n已发送市场分析到Discord，下次发送将在{DISCORD_SEND_INTERVAL}秒后")
                # 发送后清空订单变化记录和已移除订单记录
                order_changes["bids"].clear()
                order_changes["asks"].clear()
                removed_orders["bids"].clear()
                removed_orders["asks"].clear()

def on_message(ws, message):
    """处理WebSocket消息"""
    global last_update_id
    
    try:
        data = json.loads(message)
        
        # 处理订阅确认消息
        if "result" in data and "id" in data:
            print(f"订阅确认: {message}")
            return
        
        # 确保消息包含必要的字段
        if "U" not in data or "u" not in data or "b" not in data or "a" not in data:
            print(f"收到的消息格式不符合预期: {message}")
            return
        
        # 获取更新ID
        first_update_id = data["U"]
        final_update_id = data["u"]
        
        # 同步检查
        if first_update_id <= last_update_id + 1 <= final_update_id:
            # 应用更新
            apply_update(data["b"], data["a"])
            last_update_id = final_update_id
            
            # 每10次更新打印一次摘要
            if final_update_id % 10 == 0:
                print(f"更新完成，finalUpdateId: {final_update_id}")
                print_order_book_summary()
        elif first_update_id > last_update_id + 1:
            print(f"数据不连续，需重新获取快照！当前lastUpdateId: {last_update_id}, 收到U: {first_update_id}")
            # 重新获取快照
            order_book["bids"].clear()
            order_book["asks"].clear()
            get_initial_snapshot(symbol="BTCUSDT", limit=5000)
    except Exception as e:
        print(f"处理消息时出错: {e}")
        print(f"原始消息: {message}")

def on_open(ws):
    print("已连接到币安WebSocket")
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": ["btcusdt@depth"],
        "id": 1
    }
    ws.send(json.dumps(subscribe_message))

def run_websocket():
    websocket_url = "wss://stream.binance.com:9443/ws"
    ws = websocket.WebSocketApp(
        websocket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=lambda ws, error: print(f"错误: {error}"),
        on_close=lambda ws, code, msg: print("连接关闭")
    )
    ws.run_forever()

if __name__ == "__main__":
    try:
        # 步骤1：获取初始快照
        print("加载初始订单簿快照...")
        get_initial_snapshot(symbol="BTCUSDT", limit=5000)
        
        # 步骤2：启动WebSocket并维护深度
        print("\n启动WebSocket客户端...")
        run_websocket()
    except KeyboardInterrupt:
        print("\n用户中断程序")
    except Exception as e:
        print(f"发生异常: {e}")

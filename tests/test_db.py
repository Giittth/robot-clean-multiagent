from backend.db.database import get_db

# 测试数据库连接
def test_database():
    # 拿到数据库连接
    db_gen = get_db()
    conn = next(db_gen)  # 获取连接

    try:
        # 执行一条最简单 SQL：测试是否连通
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS tests")
            result = cursor.fetchone()

        print("数据库连接成功！")
        print(f"测试查询结果：{result}")

    except Exception as e:
        print("连接失败！错误信息：")
        print(e)

    finally:
        # 关闭连接
        try:
            db_gen.close()
        except:
            pass

if __name__ == "__main__":
    test_database()
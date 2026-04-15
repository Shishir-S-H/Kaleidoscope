import psycopg2, os
conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD','npg_4mNWuybHc6sD'), sslmode='require'
)
cur = conn.cursor()
cur.execute("""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_name IN (
        'media_ai_insights','media_detected_faces',
        'read_model_media_search','read_model_recommendations_knn',
        'read_model_feed_personalized','read_model_post_search','read_model_face_search'
    )
    ORDER BY table_name, ordinal_position
""")
cur_table = None
for tbl, col, dtype in cur.fetchall():
    if tbl != cur_table:
        print(f"\n[{tbl}]")
        cur_table = tbl
    print(f"  {col}  ({dtype})")
conn.close()

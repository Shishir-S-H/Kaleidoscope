import psycopg2

conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password='npg_4mNWuybHc6sD', sslmode='require'
)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='media_detected_faces' ORDER BY ordinal_position")
print("=== media_detected_faces columns ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

cur.execute("SELECT * FROM media_detected_faces LIMIT 1")
cols = [d[0] for d in cur.description]
print("\nColumns from cursor:", cols)

# Post 17 rows
cur.execute("""
    SELECT mdf.* FROM media_detected_faces mdf
    JOIN post_media pm ON pm.media_id = mdf.media_id
    WHERE pm.post_id = 17
""")
rows = cur.fetchall()
print(f"\n=== media_detected_faces for post_id=17: {len(rows)} rows ===")
for r in rows:
    for col, val in zip(cols, r):
        if col == 'embedding':
            print(f"  {col}: [vector, dims=N/A]")
        else:
            print(f"  {col}: {val}")
    print()

conn.close()

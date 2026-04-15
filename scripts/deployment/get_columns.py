import psycopg2
conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner', password='npg_4mNWuybHc6sD', sslmode='require'
)
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='read_model_post_search' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('read_model_post_search columns:', cols)

cur.execute("SELECT * FROM read_model_post_search WHERE post_id = 8")
row = cur.fetchone()
print('Row for post_id=8:', row)
conn.close()

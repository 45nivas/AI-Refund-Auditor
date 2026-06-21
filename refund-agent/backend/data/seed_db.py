import sqlite3
import os

def seed_databases():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    crm_db_path = os.path.join(data_dir, "crm.db")
    decisions_db_path = os.path.join(data_dir, "decisions.db")

    print(f"Seeding CRM database at: {crm_db_path}")
    print(f"Seeding Decisions database at: {decisions_db_path}")

    # Connect to CRM database
    conn_crm = sqlite3.connect(crm_db_path)
    cursor_crm = conn_crm.cursor()

    # Create customers table
    cursor_crm.execute("""
        DROP TABLE IF EXISTS customers
    """)
    cursor_crm.execute("""
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            order_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            order_date TEXT NOT NULL,
            order_amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            delivery_status TEXT NOT NULL,
            days_since_delivery INTEGER NOT NULL,
            previous_refund_count INTEGER NOT NULL,
            account_age_days INTEGER NOT NULL,
            order_status TEXT NOT NULL,
            return_status TEXT NOT NULL,
            is_digital INTEGER NOT NULL DEFAULT 0,
            item_condition TEXT NOT NULL DEFAULT 'perfect'
        )
    """)

    # Customer profiles to seed
    customers = [
        # 1. Clean refund (delivered 5 days ago, 0 prior refunds) -> APPROVE
        ("CUST001", "Alice Smith", "alice.smith@example.com", "ORD1001", "Wireless Headphones", "2026-06-13", 1500.00, "credit_card", "delivered", 5, 0, 120, "completed", "not_initiated", 0, "perfect"),
        # 2. Delivered 35 days ago -> DENY (past 30-day window)
        ("CUST002", "Bob Jones", "bob.jones@example.com", "ORD1002", "Leather Wallet", "2026-05-14", 800.00, "UPI", "delivered", 35, 0, 95, "completed", "not_initiated", 0, "perfect"),
        # 3. In transit -> DENY (not yet delivered)
        ("CUST003", "Charlie Brown", "charlie.b@example.com", "ORD1003", "Running Shoes", "2026-06-17", 4500.00, "COD", "in_transit", 0, 0, 45, "completed", "not_initiated", 0, "perfect"),
        # 4. 3 prior refunds -> DENY (abuse policy)
        ("CUST004", "Diana Prince", "diana.prince@example.com", "ORD1004", "Phone Case", "2026-06-16", 500.00, "credit_card", "delivered", 2, 3, 200, "completed", "not_initiated", 0, "perfect"),
        # 5. COD order, return not shipped back -> DENY
        ("CUST005", "Ethan Hunt", "ethan.hunt@example.com", "ORD1005", "Mechanical Keyboard", "2026-06-08", 2500.00, "COD", "delivered", 10, 0, 150, "completed", "not_initiated", 0, "perfect"),
        # 6. Partial refund eligible (damaged item, keep product) -> PARTIAL
        ("CUST006", "Fiona Gallagher", "fiona.g@example.com", "ORD1006", "Coffee Maker", "2026-06-14", 3000.00, "UPI", "delivered", 4, 1, 80, "completed", "not_initiated", 0, "damaged"),
        # 7. High-value order > ₹10,000 -> ESCALATE
        ("CUST007", "George Clark", "george.clark@example.com", "ORD1007", "Smart Watch", "2026-06-15", 12000.00, "credit_card", "delivered", 3, 0, 365, "completed", "not_initiated", 0, "perfect"),
        # 8. Cancelled order, payment not reversed -> APPROVE
        ("CUST008", "Hannah Abbott", "hannah.a@example.com", "ORD1008", "Gaming Mouse", "2026-06-18", 4500.00, "credit_card", "not_shipped", 0, 0, 30, "cancelled", "not_initiated", 0, "perfect"),
        # 9. Digital product -> DENY (digital non-refundable)
        ("CUST009", "Ian Malcolm", "ian.m@example.com", "ORD1009", "SaaS Pro License", "2026-06-17", 999.00, "UPI", "delivered", 1, 0, 60, "completed", "not_initiated", 1, "perfect"),
        # 10. COD order, return initiated/returned -> APPROVE
        ("CUST010", "Julia Roberts", "julia.r@example.com", "ORD1010", "Canvas Backpack", "2026-06-10", 1800.00, "COD", "delivered", 8, 1, 500, "completed", "returned", 0, "perfect"),
        # 11. Disputed completed order -> ESCALATE (escalate disputed status)
        ("CUST011", "Kevin Bacon", "kevin.bacon@example.com", "ORD1011", "Electric Kettle", "2026-06-06", 3200.00, "UPI", "delivered", 12, 0, 15, "disputed", "not_initiated", 0, "perfect"),
        # 12. Multiple policy violations (past window & 3 refunds) -> DENY
        ("CUST012", "Laura Croft", "laura.c@example.com", "ORD1012", "Table Lamp", "2026-05-09", 1500.00, "COD", "delivered", 40, 3, 250, "completed", "not_initiated", 0, "perfect"),
        # 13. Clean refund 2 -> APPROVE
        ("CUST013", "Mike Myers", "mike.m@example.com", "ORD1013", "Winter Jacket", "2026-06-03", 4000.00, "credit_card", "delivered", 15, 1, 180, "completed", "returned", 0, "perfect"),
        # 14. Partial refund eligible (damaged, keep product) -> PARTIAL
        ("CUST014", "Nancy Drew", "nancy.drew@example.com", "ORD1014", "Ergonomic Desk Mat", "2026-06-11", 5000.00, "UPI", "delivered", 7, 0, 75, "completed", "not_initiated", 0, "damaged"),
        # 15. In transit & High Value -> DENY/ESCALATE (first priority is delivery check -> deny refund request since in_transit)
        ("CUST015", "Oscar Wilde", "oscar.w@example.com", "ORD1015", "Home Projector", "2026-06-17", 15000.00, "credit_card", "in_transit", 0, 0, 400, "completed", "not_initiated", 0, "perfect")
    ]

    cursor_crm.executemany("""
        INSERT INTO customers (
            customer_id, name, email, order_id, product_name, order_date, 
            order_amount, payment_method, delivery_status, days_since_delivery, 
            previous_refund_count, account_age_days, order_status, return_status,
            is_digital, item_condition
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, customers)

    conn_crm.commit()
    conn_crm.close()
    print("Successfully seeded customers in crm.db.")

    # Connect to Decisions database
    conn_dec = sqlite3.connect(decisions_db_path)
    cursor_dec = conn_dec.cursor()

    # Create decisions table
    cursor_dec.execute("""
        DROP TABLE IF EXISTS decisions
    """)
    cursor_dec.execute("""
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            name TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            agent_notes TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn_dec.commit()
    conn_dec.close()
    print("Successfully initialized decisions.db.")

if __name__ == "__main__":
    seed_databases()

# ============================================================
# DAY 01: DATABASE FUNDAMENTALS
# ============================================================

print("DAY 01 - DATABASE FUNDAMENTALS")


# ============================================================
# 1. WHAT IS DATA?
# ============================================================

print("\n1. WHAT IS DATA?")

name = "Atul"
age = 33
city = "Lucknow"

print("Name:", name)
print("Age:", age)
print("City:", city)

print("\nData is information that can be stored, processed, and used.")


# ============================================================
# 2. WHAT IS A DATABASE?
# ============================================================

print("\n2. WHAT IS A DATABASE?")

print("A database is an organized collection of data.")
print("It allows data to be stored, managed, retrieved, and updated.")


# ============================================================
# 3. RECORDS AND FIELDS
# ============================================================

print("\n3. RECORDS AND FIELDS")

student = {
    "id": 101,
    "name": "Atul",
    "course": "Computer Science",
    "score": 85
}

print("Student Record:")
print(student)

print("\nFields:")
for field in student:
    print("-", field)

print("\nA record represents one complete data entry.")
print("A field represents one attribute of that record.")


# ============================================================
# 4. TABLE
# ============================================================

print("\n4. TABLE")

students = [
    {
        "id": 101,
        "name": "Atul",
        "course": "Computer Science",
        "score": 85
    },
    {
        "id": 102,
        "name": "Rahul",
        "course": "Data Science",
        "score": 90
    },
    {
        "id": 103,
        "name": "Priya",
        "course": "Cybersecurity",
        "score": 88
    }
]

for student in students:
    print(
        student["id"],
        "|",
        student["name"],
        "|",
        student["course"],
        "|",
        student["score"]
    )


# ============================================================
# 5. PRIMARY KEY
# ============================================================

print("\n5. PRIMARY KEY")

print("Student ID can uniquely identify each student.")

for student in students:
    print("Primary Key:", student["id"])


# ============================================================
# 6. RETRIEVING DATA
# ============================================================

print("\n6. RETRIEVING DATA")

for student in students:
    if student["id"] == 102:
        print("Found Student:", student)


# ============================================================
# 7. FILTERING DATA
# ============================================================

print("\n7. FILTERING DATA")

print("Students with score greater than 85:")

for student in students:
    if student["score"] > 85:
        print(student["name"], "-", student["score"])


# ============================================================
# 8. UPDATING DATA
# ============================================================

print("\n8. UPDATING DATA")

students[0]["score"] = 92

print("Updated student:")
print(students[0])


# ============================================================
# 9. ADDING DATA
# ============================================================

print("\n9. ADDING DATA")

new_student = {
    "id": 104,
    "name": "Amit",
    "course": "Artificial Intelligence",
    "score": 91
}

students.append(new_student)

print("New student added:")
print(new_student)


# ============================================================
# 10. DELETING DATA
# ============================================================

print("\n10. DELETING DATA")

students = [
    student
    for student in students
    if student["id"] != 104
]

print("Student with ID 104 removed.")

for student in students:
    print(student)


# ============================================================
# 11. DATABASE OPERATIONS
# ============================================================

print("\n11. BASIC DATABASE OPERATIONS")

print("""
Create  → Add new data
Read    → Retrieve data
Update  → Modify existing data
Delete  → Remove data

These four operations are commonly known as CRUD.
""")


# ============================================================
# 12. WHY DATABASES ARE IMPORTANT
# ============================================================

print("\n12. WHY DATABASES ARE IMPORTANT")

print("Databases help applications:")
print("- Store large amounts of data")
print("- Retrieve information efficiently")
print("- Update existing information")
print("- Maintain organized data")
print("- Support multiple users and applications")


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("DAY 01 COMPLETED")
print("=" * 60)

print("""
Today you learned:

1. Data
2. Databases
3. Records
4. Fields
5. Tables
6. Primary Keys
7. Data Retrieval
8. Data Filtering
9. Data Updating
10. Data Addition
11. Data Deletion
12. CRUD Operations
13. Importance of Databases
""")


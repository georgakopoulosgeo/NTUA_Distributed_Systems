# Dockerfile
FROM python:3.9-slim

# Ορίζουμε τον φάκελο εργασίας μέσα στο container
WORKDIR /app

# Αντιγράφουμε τα αρχεία του project στο container
COPY . /app

# Εγκαθιστούμε τις απαραίτητες βιβλιοθήκες (Flask και requests)
RUN pip install --no-cache-dir flask requests

# Ανοίγουμε την θύρα (εδώ η προεπιλεγμένη είναι η 8000, αλλά μπορείτε να την αλλάξετε)
EXPOSE 8000 8001 8002 8003 8004

# Ορίζουμε την εντολή εκκίνησης. Εδώ το container θα τρέξει τον bootstrap κόμβο.
CMD ["python", "bootstrap.py"]
"""Seed the medical knowledge base with FICTIONAL reference documents.

Every document below is an invented fixture for demos and tests. They are stored
with is_fictional=True so the UI and reports can label them honestly. They are
NEVER presented as real FDA or WHO guidance.

Usage: python -m scripts.seed_references
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Organization, ReferenceDocument
from app.services.retrieval.ingest import ingest_document

# NOTE: These product names (Zorvaxin, Cardiolamine, Glucavane, Nephrotil,
# Respirol, Lumixa, Dermacalm, Hepatrin) are FICTIONAL. No assertion is made
# that they are real, approved, or safe.
FICTIONAL_DOCS = [
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug Safety Communication (fictional fixture)",
        "title": "[FICTIONAL] Zorvaxin (zorvaxabide): new contraindication during pregnancy",
        "version": "v2",
        "source_url": "https://demo.medguard.local/docs/zorvaxin-pregnancy-v2",
        "publication_date": date(2026, 8, 21),
        "effective_date": date(2026, 8, 21),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-DSA-001"},
        "sections": [
            ("Summary", "This fictional communication states that Zorvaxin tablets are now contraindicated in pregnancy following post-marketing reports of fetal harm."),
            ("Contraindications", "Zorvaxin is contraindicated in pregnant women because of the risk of fetal harm. Women who may become pregnant should use effective contraception during treatment."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug label (fictional fixture)",
        "title": "[FICTIONAL] Cardiolamine tablets, prescribing information",
        "version": "2026-05",
        "source_url": "https://demo.medguard.local/docs/cardiolamine-label",
        "publication_date": date(2026, 5, 14),
        "effective_date": date(2026, 5, 14),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-LBL-002"},
        "sections": [
            ("Indications and Usage", "Cardiolamine is indicated for the fictional treatment of hypertension in adults."),
            ("Dosage and Administration", "The maximum recommended daily dose is 400 mg in patients with normal renal function. In patients with severe renal impairment (eGFR below 30 mL/min), do not exceed 200 mg per day."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug label (fictional fixture)",
        "title": "[FICTIONAL] Glucavane extended-release tablets, prescribing information",
        "version": "2026-07",
        "source_url": "https://demo.medguard.local/docs/glucavane-label",
        "publication_date": date(2026, 7, 9),
        "effective_date": date(2026, 7, 9),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-LBL-003"},
        "sections": [
            ("Indications and Usage", "Glucavane is indicated as an adjunct to diet and exercise to improve glycemic control in adults with fictional type 2 diabetes."),
            ("Dosage and Administration", "Initiate Glucavane at 500 mg once daily with the evening meal. Increase gradually based on tolerability. The previous twice-daily starting regimen is no longer recommended."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug Safety Communication (fictional fixture)",
        "title": "[FICTIONAL] Nephrotil: increased bleeding risk with anticoagulants",
        "version": "v1",
        "source_url": "https://demo.medguard.local/docs/nephrotil-interaction",
        "publication_date": date(2026, 9, 2),
        "effective_date": date(2026, 9, 2),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-DSA-004"},
        "sections": [
            ("Summary", "This fictional communication describes a drug interaction between Nephrotil and anticoagulant medicines."),
            ("Drug Interactions", "Concomitant use of Nephrotil with anticoagulants increases the risk of serious bleeding. Monitor patients closely and consider an alternative analgesic."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug label (fictional fixture)",
        "title": "[FICTIONAL] Respirol inhalation aerosol, prescribing information",
        "version": "2026-03",
        "source_url": "https://demo.medguard.local/docs/respirol-label",
        "publication_date": date(2026, 3, 30),
        "effective_date": date(2026, 3, 30),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-LBL-005"},
        "sections": [
            ("Indications and Usage", "Respirol is indicated for the fictional relief of bronchospasm in patients with reversible obstructive airway disease."),
            ("Pediatric Use", "Respirol is approved for use in patients 6 years of age and older. Safety and effectiveness in pediatric patients below 6 years have not been established."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug label (fictional fixture)",
        "title": "[FICTIONAL] Lumixa tablets, prescribing information",
        "version": "2026-02",
        "source_url": "https://demo.medguard.local/docs/lumixa-label",
        "publication_date": date(2026, 2, 11),
        "effective_date": date(2026, 2, 11),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-LBL-006"},
        "sections": [
            ("Indications and Usage", "Lumixa is indicated for the fictional short-term treatment of insomnia in adults."),
            ("Geriatric Use", "Clinical studies of Lumixa did not include sufficient numbers of subjects aged 65 and over to determine whether they respond differently from younger subjects."),
        ],
    },
    {
        "authority": "MedGuard Demo Corpus (fictional)",
        "doc_type": "Drug label (fictional fixture)",
        "title": "[FICTIONAL] Hepatrin tablets (human), prescribing information",
        "version": "2026-01",
        "source_url": "https://demo.medguard.local/docs/hepatrin-label",
        "publication_date": date(2026, 1, 19),
        "effective_date": date(2026, 1, 19),
        "jurisdiction": "US",
        "identifiers": {"Notice": "FICTIONAL-LBL-007"},
        "sections": [
            ("Indications and Usage", "Hepatrin is indicated to lower cholesterol in adults with fictional hyperlipidemia."),
            ("Contraindications", "Hepatrin tablets are contraindicated in patients with active liver disease. This labeling covers the human tablet formulation only."),
        ],
    },
]


def seed() -> int:
    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).limit(1))
        if org is None:
            raise SystemExit("No organization found. Run scripts/bootstrap.py first.")
        created = 0
        for spec in FICTIONAL_DOCS:
            existing = db.scalar(
                select(ReferenceDocument).where(
                    ReferenceDocument.organization_id == org.id,
                    ReferenceDocument.title == spec["title"],
                    ReferenceDocument.version == spec["version"],
                )
            )
            if existing is not None:
                if existing.chunks:
                    print(f"exists: {spec['title'][:60]}")
                    continue
                # doc row committed but ingest failed earlier — finish the ingest
                doc = existing
                ingest_document(db, doc, spec["sections"])
                print(f"re-ingested: {spec['title'][:60]}")
                continue
            doc = ReferenceDocument(
                organization_id=org.id,
                authority=spec["authority"],
                doc_type=spec["doc_type"],
                title=spec["title"],
                version=spec["version"],
                source_url=spec["source_url"],
                publication_date=spec["publication_date"],
                effective_date=spec["effective_date"],
                jurisdiction=spec["jurisdiction"],
                identifiers=spec["identifiers"],
                is_fictional=True,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            ingest_document(db, doc, spec["sections"])
            created += 1
            print(f"ingested: {spec['title'][:60]}")
        return created
    finally:
        db.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} new reference document(s).")

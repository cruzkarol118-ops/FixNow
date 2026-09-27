"""Bloque C: mide la precisión del clasificador (número para sustentación).

Split estratificado 80/20 con semilla fija sobre EJEMPLOS: reporta precisión
global y por categoría. No toca la BD.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Evalúa el clasificador de categorías (precisión global y por categoría)."

    def handle(self, *args, **options):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.model_selection import train_test_split
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.metrics import accuracy_score
        except ImportError:
            self.stderr.write("scikit-learn no está instalado.")
            return

        from core.ia import EJEMPLOS, _normalizar, _tokens_stem

        textos = [_normalizar(t) for t, _ in EJEMPLOS]
        etiquetas = [c for _, c in EJEMPLOS]
        Xtr, Xte, ytr, yte = train_test_split(
            textos, etiquetas, test_size=0.2, random_state=42, stratify=etiquetas)
        vec = TfidfVectorizer(
            tokenizer=_tokens_stem, preprocessor=None,
            lowercase=False, token_pattern=None)
        clf = MultinomialNB(fit_prior=False)
        clf.fit(vec.fit_transform(Xtr), ytr)
        pred = clf.predict(vec.transform(Xte))
        probas = clf.predict_proba(vec.transform(Xte))
        self.stdout.write(f"Muestras: {len(EJEMPLOS)} "
                          f"(train {len(Xtr)}, test {len(Xte)})")
        self.stdout.write(f"Precisión global: {accuracy_score(yte, pred):.0%}")
        for cat in sorted(set(etiquetas)):
            idx = [i for i, y in enumerate(yte) if y == cat]
            acc = sum(1 for i in idx if pred[i] == yte[i]) / len(idx) if idx else 0
            self.stdout.write(f"  {cat}: {acc:.0%} ({len(idx)} casos)")
        # Con margen (comportamiento real): lo dudoso no se sugiere.
        import numpy as np

        from core.ia import MARGEN_CONFIANZA
        orden = np.sort(probas, axis=1)
        ventaja = orden[:, -1] - orden[:, -2]
        resp = [i for i in range(len(Xte)) if ventaja[i] >= MARGEN_CONFIANZA]
        if resp:
            acc_r = sum(1 for i in resp if pred[i] == yte[i]) / len(resp)
            self.stdout.write(
                f"Con margen {MARGEN_CONFIANZA}: responde "
                f"{len(resp)}/{len(Xte)} ({len(resp) / len(Xte):.0%} cobertura) "
                f"con {acc_r:.0%} de acierto.")

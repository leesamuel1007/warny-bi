"""Build WARNY-BI canonical vocabulary used by query-intent parsing."""

from warnybi.workflows.vocab import BuildCanonicalVocabCli


if __name__ == "__main__":
    raise SystemExit(BuildCanonicalVocabCli().run())

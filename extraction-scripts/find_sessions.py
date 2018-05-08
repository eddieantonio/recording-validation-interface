#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright © 2018 Eddie Antonio Santos. All rights reserved.
# Derived from Praat scripts written by Timothy Mills
#  - extract_items.praat
#  - extract_sessions.praat

import argparse
import logging
import re
from pathlib import Path
from decimal import Decimal
from typing import Dict, NamedTuple

from pydub import AudioSegment  # type: ignore
from textgrid import TextGrid, IntervalTier  # type: ignore
from slugify import slugify  # type: ignore

from recval.normalization import normalize
from recval.recording_session import RecordingSession


here = Path('.')
logger = logging.getLogger(__name__)
info = logger.info
warn = logger.warn

parser = argparse.ArgumentParser()
parser.add_argument('master_directory', default=here, type=Path,
                    help='Where to look for session folders')
parser.add_argument('session_codes', default=here / 'speaker-codes.csv', type=Path,
                    help='A TSV that contains codes for sessions...?', nargs='?')


class RecordingInfo(NamedTuple):
    """
    All the information you could possible want to know about a recorded
    snippet.
    """
    session: RecordingSession
    speaker: str
    type: str
    timestamp: str
    transcription: str
    translation: str
    # TODO: create manifest
    # TODO: create sha256hash of manifest


class RecordingExtractor:
    """
    Extracts recordings from a directory of sessions.
    """

    def __init__(self) -> None:
        self.sessions: Dict[RecordingSession, Path] = {}

    def scan(self, root_directory: Path) -> None:
        """
        Scans the directory provided for sessions.

        For each session directory found, its TextGrid/.wav file pairs are
        scanned for words and sentences.
        """
        info('Scanning %s for sessions...', root_directory)
        for session_dir in root_directory.iterdir():
            if not session_dir.resolve().is_dir():
                info(' ... rejecting %s; not a directory', session_dir)
                continue
            self.extract_session(session_dir)

    def extract_session(self, session_dir: Path) -> None:
        session = RecordingSession.from_name(session_dir.stem)
        if session in self.sessions:
            raise RuntimeError(f"Duplicate session: {session} "
                               f"found at {self.sessions[session]}")

        info(' ... Scanning %s for .TextGrid files', session_dir)
        text_grids = list(session_dir.glob('*.TextGrid'))
        info(' ... %d text grids', len(text_grids))

        for text_grid in text_grids:
            sound_file = text_grid.with_suffix('.wav')
            # TODO: tmill's kludge for certain missing filenames???
            if not sound_file.exists():
                warn(' ... ... could not find cooresponding audio for %s',
                     text_grid)
                continue

            assert text_grid.exists() and sound_file.exists()
            info(' ... ... Matching sound file for %s', text_grid)

            # TODO: get speaker from the session-codes table?
            speaker = '???'

            info(' ... ... Extract items from %s using speaker ID %s',
                 sound_file, speaker)
            extractor = PhraseExtractor(session,
                                        AudioSegment.from_file(str(sound_file)),
                                        TextGrid.fromFile(str(text_grid)),
                                        speaker)
            extractor.extract_all()


WORD_TIER_ENGLISH = 0
WORD_TIER_CREE = 1
SENTENCE_TIER_ENGLISH = 2
SENTENCE_TIER_CREE = 3

class PhraseExtractor:
    """
    Extracts recorings from a session directory.
    """
    def __init__(self,
                 session: RecordingSession,
                 sound: AudioSegment,
                 text_grid: TextGrid,
                 speaker: str,  # Something like "ABC"
                 ) -> None:
        self.session = session
        self.sound = sound
        self.text_grid = text_grid
        self.speaker = speaker

    def extract_all(self) -> None:
        assert len(self.text_grid.tiers) >= 2, "TextGrid has too few tiers"

        info(' ... ... extracting words')
        self.extract_words(cree_tier=self.text_grid.tiers[WORD_TIER_CREE],
                           english_tier=self.text_grid.tiers[WORD_TIER_ENGLISH])

        info(' ... ... extracting sentences')
        english_word_intervals = self.text_grid.tiers[WORD_TIER_ENGLISH]
        assert is_english_tier(english_word_intervals)
        cree_sentence_intervals = self.text_grid.tiers[SENTENCE_TIER_CREE]
        assert cree_pattern.search(cree_sentence_intervals.name)

        for interval in cree_sentence_intervals:
            if not interval.mark or interval.mark.strip() == '':
                # This interval is empty, for some reason.
                continue

            transcription = normalize(interval.mark)

            start = to_milliseconds(interval.minTime)
            end = to_milliseconds(interval.maxTime)
            midtime = (interval.minTime + interval.maxTime) / 2

            # Get the sentencs's English translation.
            english_interval = english_word_intervals.intervalContaining(midtime)
            translation = normalize(english_interval.mark)

            # Snip out the sounds.
            sound_bite = self.sound[start:end]
            # tmills: normalize sound levels (some speakers are very quiet)
            sound_bite.normalize(headroom=0.1)  # dB

            # Export it.
            slug = slugify(f"sentence-{transcription}-{self.session}-{self.speaker}-{start}",
                           to_lower=True)
            sound_bite.export(str(Path('/tmp') / f"{slug}.wav"))

            # TODO: yield sentence.

    def extract_words(self, cree_tier, english_tier):
        self.extract_phrases('word', cree_tier, english_tier)

    def timestamp_within_sentence(self, timestamp: Decimal):
        """
        Return True when the timestamp is found inside a Cree sentence.
        """
        sentences = self.text_grid.tiers[SENTENCE_TIER_CREE]
        sentence = sentences.intervalContaining(timestamp)
        return sentence and sentence.mark != ''

    def extract_phrases(self, _type: str,
                        cree_tier: IntervalTier, english_tier: IntervalTier):
        assert is_cree_tier(cree_tier), cree_tier.name
        assert is_english_tier(english_tier), english_tier.name

        for interval in cree_tier:
            if not interval.mark or interval.mark.strip() == '':
                # This interval is empty, for some reason.
                continue

            transcription = normalize(interval.mark)

            start = to_milliseconds(interval.minTime)
            end = to_milliseconds(interval.maxTime)
            midtime = (interval.minTime + interval.maxTime) / 2

            # Figure out if this word belongs to a sentence.
            if _type == 'word' and self.timestamp_within_sentence(midtime):
                # It's an example sentence; leave it for the next loop.
                info(' ... ... ... %r is in a sentence', transcription)
                continue

            # Get the word's English gloss.
            english_interval = english_tier.intervalContaining(midtime)
            translation = normalize(english_interval.mark)

            # Snip out the sounds.
            sound_bite = self.sound[start:end]
            # tmills: normalize sound levels (some speakers are very quiet)
            sound_bite.normalize(headroom=0.1)  # dB

            # Export it.
            slug = slugify(f"word-{transcription}-{self.session}-{self.speaker}-{start}",
                           to_lower=True)
            sound_bite.export(str(Path('/tmp') / f"{slug}.wav"))

            # TODO: yield word

cree_pattern = re.compile(r'\b(?:cree|crk)\b', re.IGNORECASE)
english_pattern = re.compile(r'\b(?:english|eng|en)\b', re.IGNORECASE)


def is_english_tier(tier: IntervalTier) -> bool:
    return english_pattern.search(tier.name)

def is_cree_tier(tier: IntervalTier) -> bool:
    return cree_pattern.search(tier.name)


def to_milliseconds(seconds: Decimal) -> int:
    """
    Converts interval times to an integer in milliseconds.
    """
    return int(seconds * 1000)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = parser.parse_args()

    # TODO: read session-codes?
    scanner = RecordingExtractor()
    scanner.scan(root_directory=args.master_directory)

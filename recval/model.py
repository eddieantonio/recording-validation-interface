#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright © 2018 Eddie Antonio Santos. All rights reserved.

"""
The data models for the validation app.
"""

from datetime import datetime
from enum import Enum, auto
from hashlib import sha256
from os import fspath
from pathlib import Path

from flask import current_app, url_for  # type: ignore
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from sqlalchemy.orm import validates  # type: ignore
from sqlalchemy.ext.hybrid import hybrid_property  # type: ignore

from recval.normalization import normalize as normalize_utterance


db = SQLAlchemy()
Model = db.Model


class RecordingQuality(Enum):
    """
    Tag describing the quality of a recording.
    """
    clean = auto()
    unusable = auto()


class ElicitationOrigin(Enum):
    """
    How the particular phrase got it into the database in the first place.
    There are at least three sources:

     - word in the Maskwacîs dictionary.
     - word created using the Rapid Words methodology
       (https://www.sil.org/dictionaries-lexicography/rapid-word-collection-methodology)
     - word is in a sentence
    """
    maskwacîs = auto()
    rapid_words = auto()


class Phrase(db.Model):  # type: ignore
    """
    A phrase is a sentence or a word.

    A phrase has a transcription and a translation.

    Note that translation and transcription MUST be NFC normalized!

    See: http://docs.sqlalchemy.org/en/latest/orm/inheritance.html#single-table-inheritance
    """
    __tablename__ = 'phrase'

    id = db.Column(db.Integer, primary_key=True)

    # The transcription and translation are "versioned strings", with a
    # history, timestamp, and an author.
    transcription_id = db.Column(db.Text, db.ForeignKey('versioned_string.id'),
                                 nullable=False)
    translation_id = db.Column(db.Text, db. ForeignKey('versioned_string.id'),
                               nullable=False)

    # Is this a word or a phrase?
    type = db.Column(db.Text, nullable=False)

    # Maintain the relationship to the transcription
    transcription_meta = db.relationship('VersionedString',
                                         foreign_keys=[transcription_id])
    translation_meta = db.relationship('VersionedString',
                                       foreign_keys=[translation_id])
    # One phrase may have one or more recordings.
    recordings = db.relationship('Recording')

    __mapper_args__ = {
        'polymorphic_on': type,
        # Sets 'type' to null, which is (intentionally) invalid!
        'polymorphic_identity': None
    }

    def __init__(self, *, transcription, translation,  **kwargs):
        # Create versioned transcription.
        super().__init__(
            transcription_meta=VersionedString.new(value=transcription,
                                                   author_name='<unknown>'),
            translation_meta=VersionedString.new(value=translation,
                                                 author_name='<unknown>'),
            **kwargs
        )

    @hybrid_property
    def transcription(self) -> str:
        value = self.transcription_meta.value
        assert value == normalize_utterance(value)
        return value

    @transcription.setter  # type: ignore
    def transcription(self, value: str) -> None:
        # TODO: set current author.
        previous = self.transcription_meta
        self.transcription_meta = previous.derive(value, '<unknown author>')

    @transcription.expression  # type: ignore
    def transcription(cls):
        return VersionedString.value

    @hybrid_property
    def translation(self) -> str:
        value = self.translation_meta.value
        assert value == normalize_utterance(value)
        return value

    @translation.setter  # type: ignore
    def translation(self, value: str) -> None:
        # TODO: set current author.
        previous = self.translation_meta
        self.translation_meta = previous.derive(value, '<unknown author>')

    @translation.expression  # type: ignore
    def translation(cls):
        return VersionedString.value

    @property
    def translation_history(self):
        return VersionedString.query.filter_by(
            provenance_id=self.translation_meta.provenance_id
        ).all()

    @property
    def transcription_history(self):
        return VersionedString.query.filter_by(
            provenance_id=self.transcription_meta.provenance_id
        ).all()

    def update(self, field: str, value: str) -> 'Phrase':
        """
        Update the field: either a translation or a transcription.
        """
        assert field in ('translation', 'transcription')
        normalized_value = normalize_utterance(value)
        setattr(self, field, normalized_value)
        return self


class Word(Phrase):
    """
    A single word, with a translation.

    Note that translation and transcription MUST be NFC normalized!
    """

    # The elicitation origin of this term.
    origin = db.Column(db.Enum(ElicitationOrigin), nullable=True)

    # A sentence that contains this word.
    contained_within = db.Column(db.Integer, db.ForeignKey('phrase.id'),
                                 nullable=True)
    __mapper_args__ = {
        'polymorphic_identity': 'word'
    }


class Sentence(Phrase):
    """
    An entire sentence, with a translation.

    May contain one or more words.

    Note that translation and transcription MUST be NFC normalized!
    """
    # NOTE: A sentence does not have any additional properties of its own.
    __mapper_args__ = {
        'polymorphic_identity': 'sentence'
    }


class Recording(db.Model):  # type: ignore
    """
    A recording of a phrase.

    This is CONTENT-ADDRESSED memory. The "fingerprint" is a SHA-256 sum of
    the raw recording file. The file itself is converted into ds

    """
    fingerprint = db.Column(db.Text, primary_key=True)
    speaker = db.Column(db.Text, nullable=True)  # TODO: Versioned String?
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.utcnow)
    phrase_id = db.Column(db.Integer, db.ForeignKey('phrase.id'),
                          nullable=False)
    quality = db.Column(db.Enum(RecordingQuality), nullable=True)

    phrase = db.relationship('Phrase', back_populates='recordings')

    @classmethod
    def new(cls, phrase: Phrase, input_file: Path, speaker: str=None,
            fingerprint: str=None) -> 'Recording':
        """
        Create a new recording and transcode it for distribution.
        """
        assert input_file.exists()
        if fingerprint is None:
            fingerprint = compute_fingerprint(input_file)
            transcode_to_aac(input_file, fingerprint)
        return cls(fingerprint=fingerprint,
                   phrase=phrase,
                   speaker=speaker)

    @property
    def aac_path(self) -> str:
        return url_for('send_audio', filename=f"{self.fingerprint}.mp4")


class VersionedString(db.Model):  # type: ignore
    """
    A versioned string is is one with a history of what it used to be, and who
    said it.

    The actual value of a versioned string is ALWAYS normalized.
    """

    __tablename__ = 'versioned_string'

    # TODO: validator for this.
    id = db.Column(db.String, primary_key=True)
    value = db.Column(db.Text, nullable=False)

    # 'provenance' is simply the first string in the series.
    provenance_id = db.Column(db.String, db.ForeignKey('versioned_string.id'),
                              nullable=False)
    previous_id = db.Column(db.String, db.ForeignKey('versioned_string.id'),
                            nullable=True)

    provenance = db.relationship('VersionedString',
                                 foreign_keys=[provenance_id],
                                 uselist=False)
    previous = db.relationship('VersionedString',
                               foreign_keys=[previous_id],
                               uselist=False)

    # TODO: author as an entity
    author_name = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # TODO: create index on provenance to get full history

    @validates('value')
    def validate_value(self, _key, utterance):
        value = normalize_utterance(utterance)
        assert len(value) > 0
        return value

    @property
    def is_root(self) -> bool:
        return self.id == self.provenance_id

    def show(self) -> str:
        """
        Returns the VersionedString somewhat like a Git object:

        See: https://gist.github.com/masak/2415865

        TODO: test show() before and after provenance and ID are set.
        """
        def generate():
            if self.provenance and self.provenance != self.id:
                # Yield the provenance ONLY when this is a non-root commit.
                yield f"provenance {self.provenance}"
            if self.previous:
                yield f"previous {self.previous}"
            yield f"author {self.author_name}"
            yield f"date {self.timestamp:%Y-%m-%dT%H:%M:%S%z}"
            yield ''
            yield self.value
        return '\n'.join(generate())

    def compute_sha256hash(self) -> str:
        """
        Compute a hash that can be used as a ID for this versioned string.
        """
        return sha256(self.show().encode('UTF-8')).hexdigest()

    def derive(self, value: str, author_name: str) -> 'VersionedString':
        """
        Create a versioned string using this instance as its previous value.
        """
        # TODO: support for date.
        instance = type(self).new(value, author_name)
        instance.previous_id = self.id
        instance.provenance_id = self.provenance_id
        # Setting previous and provenance changed the hash,
        # so recompute it.
        instance.id = instance.compute_sha256hash()
        return instance

    @classmethod
    def new(cls, value: str, author_name: str) -> 'VersionedString':
        """
        Create a "root" versioned string.
        That is, it has no history, and its provenance is itself.
        """
        instance = cls(value=normalize_utterance(value),
                       timestamp=datetime.utcnow(),
                       author_name=author_name)

        # This is the root version.
        instance.id = instance.compute_sha256hash()
        instance.provenance_id = instance.id
        return instance


'''
I will implement this stuff in the next sprint, but I gotta get it out of
my mind first.

class Author(db.Model):
    """
    An author is allowed to create and update VersionedStrings.
    """
    email = db.Column(db.Text, primary_key=True)
'''


def compute_fingerprint(file_path: Path) -> str:
    """
    Computes the SHA-256 hash of the given audio file path.
    """
    assert file_path.suffix == '.wav', f"Expected .wav file; got {file_path}"
    with open(file_path, 'rb') as f:
        return sha256(f.read()).hexdigest()


def transcode_to_aac(recording_path: Path, fingerprint: str) -> None:
    """
    Transcodes .wav files to .aac files.
    TODO: Factor this out!
    """
    # TODO: use pydub instead of some gnarly sh command.
    from sh import ffmpeg  # type: ignore
    assert recording_path.exists(), f"Could not stat {recording_path}"
    assert len(fingerprint) == 64, f"expected fingerprint: {fingerprint!r}"

    # Determine where to read and write transcoded audio files.
    transcoded_recordings_path = Path(current_app.config['TRANSCODED_RECORDINGS_PATH']).resolve()
    assert transcoded_recordings_path.is_dir()

    out_filename = transcoded_recordings_path / f"{fingerprint}.mp4"
    if out_filename.exists():
        current_app.logger.info('File already transcoded. Skipping: %s', out_filename)
        return

    current_app.logger.info('Transcoding %s', recording_path)
    ffmpeg('-i', fspath(recording_path),
           '-nostdin',
           '-n',  # Do not overwrite existing files
           '-ac', 1,  # Mix to mono
           '-acodec', 'aac',  # Use the AAC codec
           out_filename)

import argparse
import logging
import os
import sys
from functools import partial
from typing import Optional, Set

from . import constants as c
from .enums import scorers_from_csv
from .pandas_utils import patch_pandas
from .process_data import (
  LocalDataLoader,
  filter_input_data_for_testing,
  tsv_reader,
  write_parquet_local,
  write_prescoring_output,
  write_tsv_local,
)
from .run_scoring import run_contributor_scoring, run_final_note_scoring, run_scoring

import pandas as pd


logger = logging.getLogger("birdwatch.runner")
logger.setLevel(logging.INFO)


def parse_args():
  parser = argparse.ArgumentParser("Community Notes Scoring")
  parser.add_argument(
    "--check-flips",
    dest="check_flips",
    help="Validate that note statuses align with prior runs (disable for testing)",
    action="store_true",
  )
  parser.add_argument(
    "--nocheck-flips",
    help="Disable validation that note statuses align with prior runs (use for testing)",
    action="store_false",
    dest="check_flips",
  )
  parser.set_defaults(check_flips=False)
  parser.add_argument(
    "--enforce-types",
    dest="enforce_types",
    help="Raise errors when types in Pandas operations do not meet expectations.",
    action="store_true",
  )
  parser.add_argument(
    "--noenforce-types",
    dest="enforce_types",
    help="Log to stderr when types in Pandas operations do not meet expectations.",
    action="store_false",
  )
  parser.set_defaults(enforce_types=False)
  parser.add_argument(
    "-e", "--enrollment", default=c.enrollmentInputPath, help="note enrollment dataset"
  )
  parser.add_argument(
    "--epoch-millis",
    default=None,
    type=float,
    dest="epoch_millis",
    help="timestamp in milliseconds since epoch to treat as now",
  )
  parser.add_argument(
    "--headers",
    dest="headers",
    help="First row of input files should be a header",
    action="store_true",
  )
  parser.add_argument(
    "--noheaders",
    dest="headers",
    help="First row of input files should be data.  There should be no headers.",
    action="store_false",
  )
  parser.set_defaults(headers=True)
  parser.add_argument("-n", "--notes", default=c.notesInputPath, help="note dataset")
  parser.add_argument(
    "--previous-scored-notes", default=None, help="previous scored notes dataset path"
  )
  parser.add_argument(
    "--previous-aux-note-info", default=None, help="previous aux note info dataset path"
  )
  parser.add_argument(
    "--previous-rating-cutoff-millis",
    default=None,
    type=int,
    help="previous rating cutoff millis",
  )
  parser.add_argument("-o", "--outdir", default=".", help="directory for output files")
  parser.add_argument(
    "--pseudoraters",
    dest="pseudoraters",
    help="Include calculation of pseudorater intervals",
    action="store_true",
  )
  parser.add_argument(
    "--nopseudoraters",
    dest="pseudoraters",
    help="Exclude calculation of pseudorater intervals (faster)",
    action="store_false",
  )
  parser.set_defaults(pseudoraters=True)
  parser.add_argument("-r", "--ratings", default=c.ratingsInputPath, help="rating dataset")
  parser.add_argument(
    "--scorers",
    default=None,
    type=scorers_from_csv,
    help="CSV list of scorers to enable. Restricts both prescoring and final scoring "
    "to fit only these scorers. Note: prescoring artifacts saved with a restricted "
    "scorer set are only reusable (via --prescoring-indir) with the same scorer set.",
  )
  parser.add_argument(
    "--drop-participant-ids",
    default=None,
    dest="drop_participant_ids",
    help="Path to a file with one participant ID per line. If set, ratings are filtered "
    "to drop those whose raterParticipantId is in the set, and notes are filtered to drop "
    "those whose noteAuthorParticipantId is in the set. Intended for ablations that reuse "
    "shared prescoring artifacts (via --prescoring-indir) across many filtered final-"
    "scoring runs.",
  )
  parser.add_argument(
    "--seed", default=None, type=int, help="set to an int to seed matrix factorization"
  )
  parser.add_argument(
    "-s",
    "--status",
    default=c.noteStatusHistoryInputPath,
    help="note status history dataset",
  )
  parser.add_argument(
    "--strict-columns",
    dest="strict_columns",
    help="Explicitly select columns and require that expected columns are present.",
    action="store_true",
  )
  parser.add_argument(
    "--nostrict-columns",
    help="Disable validation of expected columns and allow unexpected columns.",
    action="store_false",
    dest="strict_columns",
  )
  parser.set_defaults(strict_columns=True)
  parser.add_argument(
    "--parallel",
    help="Enable parallel run of algorithm.",
    action="store_true",
    dest="parallel",
  )
  parser.set_defaults(parallel=False)

  parser.add_argument(
    "--no-parquet",
    help="Disable writing parquet files.",
    default=False,
    action="store_true",
    dest="no_parquet",
  )

  parser.add_argument(
    "--cutoff-timestamp-millis",
    default=None,
    type=int,
    dest="cutoffTimestampMillis",
    help="filter notes and ratings created after this time.",
  )
  parser.add_argument(
    "--exclude-ratings-after-a-note-got-first-status-plus-n-hours",
    default=None,
    type=int,
    dest="excludeRatingsAfterANoteGotFirstStatusPlusNHours",
    help="Exclude ratings after a note got first status plus n hours",
  )
  parser.add_argument(
    "--days-in-past-to-apply-post-first-status-filtering",
    default=14,
    type=int,
    dest="daysInPastToApplyPostFirstStatusFiltering",
    help="Days in past to apply post first status filtering",
  )
  parser.add_argument(
    "--prescoring-delay-hours",
    default=None,
    type=int,
    dest="prescoring_delay_hours",
    help="Filter prescoring input to simulate delay in hours",
  )
  parser.add_argument(
    "--sample-ratings",
    default=0.0,
    type=float,
    dest="sample_ratings",
    help="Set to sample ratings at random.",
  )
  parser.add_argument(
    "--prescoring-outdir",
    default=None,
    dest="prescoring_outdir",
    help="If set, write prescoring outputs (note/rater model output, classifiers, meta) "
    "to this directory so a later final-only run can load them.",
  )
  parser.add_argument(
    "--prescoring-indir",
    default=None,
    dest="prescoring_indir",
    help="If set, skip prescoring and load prescoring artifacts from this directory "
    "(written by a previous run with --prescoring-outdir).",
  )
  return parser.parse_args()


@patch_pandas
def _run_scorer(
  args=None,
  dataLoader=None,
  extraScoringArgs={},
):
  logger.info("beginning scorer execution")
  assert args is not None, "args must be available"
  if args.epoch_millis:
    c.epochMillis = args.epoch_millis
    c.useCurrentTimeInsteadOfEpochMillisForNoteStatusHistory = False

  # Load input dataframes.
  if dataLoader is None:
    dataLoader = LocalDataLoader(
      args.notes,
      args.ratings,
      args.status,
      args.enrollment,
      args.headers,
    )
  notes, ratings, statusHistory, userEnrollment = dataLoader.get_data()
  dropIds: Optional[Set[str]] = None
  droppedNoteIds: Optional[Set[int]] = None
  if args.drop_participant_ids is not None:
    with open(args.drop_participant_ids) as f:
      dropIds = {line.strip() for line in f if line.strip()}
    origNotes, origRatings, origStatus, origEnroll = (
      len(notes),
      len(ratings),
      len(statusHistory),
      len(userEnrollment),
    )
    origAuthors = notes[c.noteAuthorParticipantIdKey].astype(str).nunique()
    origRaters = ratings[c.raterParticipantIdKey].astype(str).nunique()
    droppedNoteIds = set(
      notes.loc[notes[c.noteAuthorParticipantIdKey].astype(str).isin(dropIds), c.noteIdKey]
    )
    notes = notes[~notes[c.noteAuthorParticipantIdKey].astype(str).isin(dropIds)]
    ratings = ratings[
      ~ratings[c.raterParticipantIdKey].astype(str).isin(dropIds)
      & ~ratings[c.noteIdKey].isin(droppedNoteIds)
    ]
    statusHistory = statusHistory[~statusHistory[c.noteIdKey].isin(droppedNoteIds)]
    userEnrollment = userEnrollment[
      ~userEnrollment[c.participantIdKey].astype(str).isin(dropIds)
    ]
    postAuthors = notes[c.noteAuthorParticipantIdKey].astype(str).nunique()
    postRaters = ratings[c.raterParticipantIdKey].astype(str).nunique()
    logger.info(
      f"drop-participant-ids ({len(dropIds)} ids, {len(droppedNoteIds)} authored notes): "
      f"notes {origNotes}->{len(notes)}, "
      f"ratings {origRatings}->{len(ratings)}, "
      f"statusHistory {origStatus}->{len(statusHistory)}, "
      f"userEnrollment {origEnroll}->{len(userEnrollment)}, "
      f"unique authors {origAuthors}->{postAuthors}, "
      f"unique raters {origRaters}->{postRaters}"
    )
    leakedAuthors = set(notes[c.noteAuthorParticipantIdKey].astype(str)) & dropIds
    leakedRaters = set(ratings[c.raterParticipantIdKey].astype(str)) & dropIds
    leakedNotes = set(notes[c.noteIdKey]) & droppedNoteIds
    leakedStatusNotes = set(statusHistory[c.noteIdKey]) & droppedNoteIds
    leakedRatingNotes = set(ratings[c.noteIdKey]) & droppedNoteIds
    leakedEnroll = set(userEnrollment[c.participantIdKey].astype(str)) & dropIds
    assert not leakedAuthors, (
      f"drop-participant-ids leak: {len(leakedAuthors)} dropped authors still in notes "
      f"(e.g. {list(leakedAuthors)[:3]})"
    )
    assert not leakedRaters, (
      f"drop-participant-ids leak: {len(leakedRaters)} dropped raters still in ratings "
      f"(e.g. {list(leakedRaters)[:3]})"
    )
    assert not leakedNotes, (
      f"drop-participant-ids leak: {len(leakedNotes)} dropped-author notes still in notes df"
    )
    assert not leakedStatusNotes, (
      f"drop-participant-ids leak: {len(leakedStatusNotes)} dropped-author notes still in noteStatusHistory"
    )
    assert not leakedRatingNotes, (
      f"drop-participant-ids leak: {len(leakedRatingNotes)} ratings on dropped-author notes still present"
    )
    assert not leakedEnroll, (
      f"drop-participant-ids leak: {len(leakedEnroll)} dropped participants still in userEnrollment"
    )
  if args.previous_scored_notes is not None:
    previousScoredNotes = tsv_reader(
      args.previous_scored_notes,
      c.noteModelOutputTSVTypeMapping,
      c.noteModelOutputTSVColumns,
      header=False,
      convertNAToNone=False,
    )
    assert (
      args.previous_aux_note_info is not None
    ), "previous_aux_note_info must be available if previous_scored_notes is available"
    previousAuxiliaryNoteInfo = tsv_reader(
      args.previous_aux_note_info,
      c.auxiliaryScoredNotesTSVTypeMapping,
      c.auxiliaryScoredNotesTSVColumns,
      header=False,
      convertNAToNone=False,
    )
  else:
    previousScoredNotes = None
    previousAuxiliaryNoteInfo = None

  # Sample ratings to decrease runtime
  if args.sample_ratings:
    origSize = len(ratings)
    ratings = ratings.sample(frac=args.sample_ratings)
    logger.info(f"ratings reduced from {origSize} to {len(ratings)}")

  # If requested, persist prescoring outputs so future runs can skip prescoring.
  writePrescoringScoringOutputCallback = None
  if args.prescoring_outdir is not None:
    os.makedirs(args.prescoring_outdir, exist_ok=True)
    d = args.prescoring_outdir
    writePrescoringScoringOutputCallback = partial(
      write_prescoring_output,
      noteModelOutputPath=os.path.join(d, "prescoring_note_model_output.tsv"),
      raterModelOutputPath=os.path.join(d, "prescoring_rater_model_output.tsv"),
      noteTopicClassifierPath=os.path.join(d, "prescoring_note_topic_classifier.joblib"),
      pflipClassifierPath=os.path.join(d, "prescoring_pflip_classifier.bin"),
      prescoringMetaOutputPath=os.path.join(d, "prescoring_meta_output.joblib"),
      prescoringScoredNotesOutputPath=os.path.join(d, "prescoring_scored_notes.tsv"),
      headers=args.headers,
    )

  if args.prescoring_indir is not None:
    # Final-only path: load prescoring artifacts and skip the prescorer.
    d = args.prescoring_indir
    presLoader = LocalDataLoader(
      args.notes,
      args.ratings,
      args.status,
      args.enrollment,
      args.headers,
      prescoringNoteModelOutputPath=os.path.join(d, "prescoring_note_model_output.tsv"),
      prescoringRaterModelOutputPath=os.path.join(d, "prescoring_rater_model_output.tsv"),
      prescoringNoteTopicClassifierPath=os.path.join(d, "prescoring_note_topic_classifier.joblib"),
      prescoringPflipClassifierPath=os.path.join(d, "prescoring_pflip_classifier.bin"),
      prescoringMetaOutputPath=os.path.join(d, "prescoring_meta_output.joblib"),
    )
    (
      preNoteOutput,
      preRaterOutput,
      topicClassifier,
      pflipClassifier,
      preMetaOutput,
    ) = presLoader.get_prescoring_model_output()

    if dropIds is not None:
      origPreRater, origPreNote = len(preRaterOutput), len(preNoteOutput)
      preRaterOutput = preRaterOutput[
        ~preRaterOutput[c.raterParticipantIdKey].astype(str).isin(dropIds)
      ]
      preNoteOutput = preNoteOutput[~preNoteOutput[c.noteIdKey].isin(droppedNoteIds)]
      logger.info(
        f"drop-participant-ids: prescoringRaterModelOutput {origPreRater}->{len(preRaterOutput)}, "
        f"prescoringNoteModelOutput {origPreNote}->{len(preNoteOutput)}"
      )
      leakedPreRater = set(preRaterOutput[c.raterParticipantIdKey].astype(str)) & dropIds
      leakedPreNote = set(preNoteOutput[c.noteIdKey]) & droppedNoteIds
      assert not leakedPreRater, (
        f"drop-participant-ids leak: {len(leakedPreRater)} dropped raters still in prescoringRaterModelOutput"
      )
      assert not leakedPreNote, (
        f"drop-participant-ids leak: {len(leakedPreNote)} dropped-author notes still in prescoringNoteModelOutput"
      )

    notes, ratings, _, _ = filter_input_data_for_testing(
      notes,
      ratings,
      statusHistory,
      args.cutoffTimestampMillis,
      args.excludeRatingsAfterANoteGotFirstStatusPlusNHours,
      args.daysInPastToApplyPostFirstStatusFiltering,
      args.prescoring_delay_hours,
    )

    scoredNotes, newStatus, auxNoteInfo, _ = run_final_note_scoring(
      args,
      notes=notes,
      ratings=ratings,
      noteStatusHistory=statusHistory,
      userEnrollment=userEnrollment,
      prescoringNoteModelOutput=preNoteOutput,
      prescoringRaterModelOutput=preRaterOutput,
      noteTopicClassifier=topicClassifier,
      pflipClassifier=pflipClassifier,
      prescoringMetaOutput=preMetaOutput,
      seed=args.seed,
      pseudoraters=args.pseudoraters,
      enabledScorers=args.scorers,
      strictColumns=args.strict_columns,
      runParallel=args.parallel,
      dataLoader=presLoader if args.parallel else None,
      checkFlips=args.check_flips,
      previousScoredNotes=previousScoredNotes,
      previousAuxiliaryNoteInfo=previousAuxiliaryNoteInfo,
      previousRatingCutoffTimestampMillis=args.previous_rating_cutoff_millis,
      dropParticipantIds=dropIds,
      droppedNoteIds=droppedNoteIds,
    )
    helpfulnessScores = run_contributor_scoring(
      ratings=ratings,
      scoredNotes=scoredNotes,
      auxiliaryNoteInfo=auxNoteInfo,
      prescoringRaterModelOutput=preRaterOutput,
      noteStatusHistory=newStatus,
      userEnrollment=userEnrollment,
      strictColumns=args.strict_columns,
      enabledScorers=args.scorers,
      dropParticipantIds=dropIds,
      droppedNoteIds=droppedNoteIds,
    )
  else:
    # Combined path: prescoring + final scoring + contributor scoring.
    scoredNotes, helpfulnessScores, newStatus, auxNoteInfo = run_scoring(
      args,
      notes,
      ratings,
      statusHistory,
      userEnrollment,
      seed=args.seed,
      pseudoraters=args.pseudoraters,
      enabledScorers=args.scorers,
      strictColumns=args.strict_columns,
      runParallel=args.parallel,
      dataLoader=dataLoader if args.parallel == True else None,
      writePrescoringScoringOutputCallback=writePrescoringScoringOutputCallback,
      cutoffTimestampMillis=args.cutoffTimestampMillis,
      excludeRatingsAfterANoteGotFirstStatusPlusNHours=args.excludeRatingsAfterANoteGotFirstStatusPlusNHours,
      daysInPastToApplyPostFirstStatusFiltering=args.daysInPastToApplyPostFirstStatusFiltering,
      filterPrescoringInputToSimulateDelayInHours=args.prescoring_delay_hours,
      checkFlips=args.check_flips,
      previousScoredNotes=previousScoredNotes,
      previousAuxiliaryNoteInfo=previousAuxiliaryNoteInfo,
      previousRatingCutoffTimestampMillis=args.previous_rating_cutoff_millis,
      **extraScoringArgs,
    )

  # Final output-side leak guard: nothing dropped should appear in any of the four
  # outputs that are about to be written to disk.
  if dropIds is not None:
    leakedScoredAuthors = set(scoredNotes[c.noteIdKey]) & droppedNoteIds
    leakedHelpRaters = set(helpfulnessScores[c.raterParticipantIdKey].astype(str)) & dropIds
    leakedStatusOut = set(newStatus[c.noteIdKey]) & droppedNoteIds
    leakedAuxOut = set(auxNoteInfo[c.noteIdKey]) & droppedNoteIds
    assert not leakedScoredAuthors, (
      f"output leak: {len(leakedScoredAuthors)} dropped-author notes in scored_notes.tsv"
    )
    assert not leakedHelpRaters, (
      f"output leak: {len(leakedHelpRaters)} dropped raters in helpfulness_scores.tsv "
      f"(e.g. {list(leakedHelpRaters)[:3]})"
    )
    assert not leakedStatusOut, (
      f"output leak: {len(leakedStatusOut)} dropped-author notes in note_status_history.tsv"
    )
    assert not leakedAuxOut, (
      f"output leak: {len(leakedAuxOut)} dropped-author notes in aux_note_info.tsv"
    )

  # Write outputs to local disk.
  write_tsv_local(scoredNotes, os.path.join(args.outdir, "scored_notes.tsv"))
  write_tsv_local(helpfulnessScores, os.path.join(args.outdir, "helpfulness_scores.tsv"))
  write_tsv_local(newStatus, os.path.join(args.outdir, "note_status_history.tsv"))
  write_tsv_local(auxNoteInfo, os.path.join(args.outdir, "aux_note_info.tsv"))

  if not args.no_parquet:
    write_parquet_local(scoredNotes, os.path.join(args.outdir, "scored_notes.parquet"))
    write_parquet_local(helpfulnessScores, os.path.join(args.outdir, "helpfulness_scores.parquet"))
    write_parquet_local(newStatus, os.path.join(args.outdir, "note_status_history.parquet"))
    write_parquet_local(auxNoteInfo, os.path.join(args.outdir, "aux_note_info.parquet"))


def main(
  args=None,
  dataLoader=None,
  extraScoringArgs={},
):
  if args is None:
    args = parse_args()
  logger.info(f"scorer python version: {sys.version}")
  logger.info(f"scorer pandas version: {pd.__version__}")
  # patch_pandas requires that args are available (which matches the production binary) so
  # we first parse the arguments then invoke the decorated _run_scorer.
  return _run_scorer(args=args, dataLoader=dataLoader, extraScoringArgs=extraScoringArgs)


if __name__ == "__main__":
  main()

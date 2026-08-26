"""Canonical discovered-job domain model.

``JobPosting != Application``: a DiscoveredJob is a vacancy the system knows
exists; an application is a vacancy the user has decided to pursue. These
concepts must never be merged at the model level.
"""

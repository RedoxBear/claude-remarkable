"""Document model — UUID structure, metadata, content, pagedata."""
# Handles the on-device file layout:
#   {UUID}.pdf / .epub      — original file
#   {UUID}.metadata         — title, parent, modified
#   {UUID}.content          — page order, file type
#   {UUID}.pagedata         — per-page template names
#   {UUID}/{pageNum}.rm     — binary annotation strokes (v6)

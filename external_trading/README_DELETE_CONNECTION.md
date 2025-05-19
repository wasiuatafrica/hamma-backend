# Delete External Connection Endpoint

## View
A `delete_connection` action was added to `ExternalConnectionViewSet` in `views.py`. This allows deleting a connection via:

    DELETE /external_trading/connections/{pk}/delete_connection/

## URL
No manual URL entry is needed; the DRF router exposes this action automatically as a detail route.

## Usage
Send a DELETE request to the endpoint above, authenticated as the connection owner.

---

This was added as requested. If you need a custom URL or want to allow deletion via the standard `destroy` action (DELETE on `/connections/{pk}/`), let me know.

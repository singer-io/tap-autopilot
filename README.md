# tap-autopilot

[![CircleCI](https://circleci.com/gh/singer-io/tap-autopilot.svg?style=svg)](https://circleci.com/gh/singer-io/tap-autopilot)

This is a [Singer](https://singer.io) tap that produces JSON-formatted data following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:
- Pulls raw data from Autopilot's [REST API](http://docs.autopilot.apiary.io/)
- Extracts the following resources from Autopilot
  - [Contacts](http://docs.autopilot.apiary.io/#reference/api-methods/get-all-contacts/get-all-contacts)
  - [Lists](http://docs.autopilot.apiary.io/#reference/api-methods/lists/get-list-of-lists)
  - [List's Contacts](http://docs.autopilot.apiary.io/#reference/api-methods/get-contacts-on-list/get-contacts-on-list)
  - [Smart Segments](http://docs.autopilot.apiary.io/#reference/api-methods/smart-segments/get-list-of-smart-segments)
  - [Smart Segment's Contacts](http://docs.autopilot.apiary.io/#reference/api-methods/get-contacts-on-smart-segment/get-contacts-on-smart-segment)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state
## Quick start

1. Install

    ```bash
    > pip install tap-autopilot
    ```

2. Get your Autopilot API Key

    Login to your Autopilot account, navigate to your account settings and then to the Autopilot API section. Generate a New API Key, you'll need it for the next step.

3. Create the config file

    Create a JSON file called `config.json` containing the api key you just generated and a start date, the tap will only return contacts who have been updated after the date chosen.
    Start dates should conform to the [RFC3339 specification](https://www.ietf.org/rfc/rfc3339.txt).

    ```json
    {
        "api_key": "your-autopilot-api-token",
        "start_date": "2017-01-01T00:00:00Z"
    }
    ```

4. Discover and Catalog

    Use the discover flag to explore the schema for each of this tap's resources

    ```bash
    > tap-autopulot --config config.json --discover
    ```

    Pipe the output of this file to a file that will serve as the catalog, where you will select which streams and properties to sync

    ```bash
    > touch catalog.json
    > tap-autopilot --config config.json --discover >> catalog.json
    ```

    The catalog is an object with a key streams that has an array of the streams for this tap. For each stream you want to sync, add a `"selected": true` property on the stream object. Below is an example of how you would select to sync the contacts stream. This property is recursive so it will select all children. If you don't want to sync a property, you can add `"selected": false` on that property.

    ```json
            {
            "schema": {
                "properties": {...},
                "type": "object",
                "selected": true
            },
            "stream": "contacts",
            "tap_stream_id": "contacts"
        }
    ```

5. [Optional] Add additional optional config parameters

    You can include a `user_agent` key in your `config.json` to further customize the behavior of this Tap.
    - `user_agent` should be set to something that includes a contact email address should the API provider need to contact you for any reason.

    If you were to use the `user_agent`, your complete config.json should look something like this.

    ```json
    {
      "api_key": "your-api-token",
      "start_date": "2017-01-01T00:00:00Z",
      "user_agent": "Stitch (+support@stitchdata.com)"
    }
    ```

6. [Optional] Create the initial state file

    You can provide JSON file that contains a date for the API endpoints
    to force the application to only fetch data newer than those dates.
    If you omit the file it will fetch all Autopilot data. State Files will be created for you after a successful run and will keep the status of the previous run for the next time it is invoked.

    ```json
    {
      "contacts": "2017-01-17T20:32:05Z"
    }
    ``

7. Run the application

    `tap-autopilot` can be run with:

    ```bash
    tap-autopilot --config config.json --catalog catalog.json [--state state.json]
    ```

---

Copyright &copy; 2017 Stitch

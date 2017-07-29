# tap-autopilot

This is a [Singer](https://singer.io) tap that produces JSON-formatted data following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:
- Pulls raw data from Autopilot's [REST API](http://docs.autopilot.apiary.io/)
- Extracts the following resources from Autopilot
  - [Contacts](hhttp://docs.autopilot.apiary.io/#reference/api-methods/get-all-contacts/get-all-contacts)
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

    Create a JSON file called `config.json` containing the api key you just generated.

    ```json
    {"api_key": "your-api-token"}
    ```

4. [Optional] Add additional optional config parameters

    You can include two other key-value pairs in your `config.json` to further customize the behavior of this Tap.
    - `start_date` indicates how far back Autopilot should retrieve Contacts data in the absence of a State file, all of the other streams will fully sync on every run. Start dates should conform to the [RFC3339 specification](https://www.ietf.org/rfc/rfc3339.txt).
    - `user_agent` should be set to something that includes a contact email address should the API provider need to contact you for any reason.

    If you were to use both of these, your complete config.json should look something like this.

    ```json
    {
      "api_key": "your-api-token",
      "start_date": "2017-01-01T00:00:00Z",
      "user_agent": "Stitch (+support@stitchdata.com)"
    }
    ```

5. [Optional] Create the initial state file

    You can provide JSON file that contains a date for the API endpoints
    to force the application to only fetch data newer than those dates.
    If you omit the file it will fetch all Autopilot data. State Files will be created for you after a successful run and will keep the status of the previous run for the next time it is invoked.

    ```json
    {
      "contacts": "2017-01-17T20:32:05Z"
    }
    ``

6. Run the application

    `tap-autopilot` can be run with:

    ```bash
    tap-autopilot --config config.json [--state state.json]
    ```

---

Copyright &copy; 2017 Stitch

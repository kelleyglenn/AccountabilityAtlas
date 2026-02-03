# Future Features

## UI

1. **Admin Edits**: Admin needs to be able to edit anything in a video.
2. **Moderator Edits**: Allows them to make tweaks without rejecting the submission.
3. **Video trim**: Indicate where the critical scene is
4. **Problem Flag**: Indicate if the encounters had issues or were relatively smooth.
5. **Original Video Link**: Useful for re-audits, re-cuts, or analyses of original video. Works best if the original video has already been approved in the system. If not, maybe we can auto-import it?
6. **Rating System**: Collect rating of encounter. Include the auditor rating and government official rating.

## AI

1. **Natural Language Search**: Use NLQ/NLP/LLMs to convert a simple text request from the user into a query. Probably only for Pro users, because of the potential cost.

## Social

1. **Create Primary Accounts**: YouTube, Facebook
2. **Create Secondary Accounts**: Instagram, Reddit
3. **Create Tertiary Accounts**: X, BlueSky, Discord
4. **Group Notifications**: Automatically publish notifications to chat services (Facebook, Reddit, X, BlueSky, Discord) when new videos are approved for respected auditors.
5. **Personal Notifications**: Like below, but targeted to social media accounts. Requires collecting and verifying their account info.

## Notifications

1. **Public Daily summary**: Allow registered users (as long as we know their email) to request daily email notifications that contain the day's latest additions. Consider CAN-SPAM. Possibly use a 3rd party.
2. **Custom Daily summary**: Allow registered users (as long as we know their email) to request email notifications when new videos in a defined area are approved. Allow other filter criteria as well. Possibly only for Pro users. Consider CAN-SPAM.
3. **Email templates**: Functionality probably provided by email notification provider, otherwise build custom.
4. **Immediate notification**: Email or SMS when a new video is approved with less delay (hourly job?). Pro users only.
5. **Promotions**: Notify users when they are promoted and celebrate!
6. **Upsell**: Gently notify promoted users they can go Pro.

## Import

1. **Respected List**: Create table of the respected auditors 
1. **Seed Imports**:
    - Populate the respected auditors table with the largest, most respected auditors (like LIA and HYH). Determine how far back we want to go with imports.
    - Create a job to import existing videos from respected auditors table. Seeds the DB with quality. Learning experience.
    - Add **more** respected auditors (like AtA, AP, James Freeman, etc). Gets a critical mass.
3. **Ongoing**: Create a new job for daily query for additional videos from respected auditors.

## Monetization

See ChatGPT suggestions at https://chatgpt.com/share/6981a103-1008-8010-bc2d-06927edbf2f9

1. **Donations**: Unobtrusive soft request at the bottom of each page. A donation page should break down actual costs.
2. **Advertising**: Keep these simple as well, and only focus on appropriate product and service categories.
3. **Pro Users**: Keep the price low. Sell softly only. Try to make the features compelling. Possibly a link to Patreon? Requires some form of payment processing. Keep it simple.

## Legal

1. **Privacy Policy**: A versioned and dated document that outlines what we do with the data we collect. The latest is visible to all users.
2. **Terms and Conditions**: A versioned and dated document new users must agree to when they register. Record the acceptance and the version. Old versions remain accessible.


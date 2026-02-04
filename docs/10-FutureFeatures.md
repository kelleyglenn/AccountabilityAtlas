# Future Features

## Short-term Roadmap
See [ChatGPT suggestions](https://chatgpt.com/s/t_6982deeabf6c8191b7753430621ec4fc)
1. **Curated Auditors**
2. **Seed Imports** - latest 100 videos from each, update location, amendments, participants only
3. **Privacy Policy**
4. **Terms and Conditions**
5. **Donations**

## UI

1. **Admin Edits**: Admin needs to be able to edit anything in a video.
2. **Moderator Edits**: Allows moderators to make tweaks while reviewing without rejecting the submission. This can include fine-tuning the location (define some limits) and providing missing or incorrect data, such as amendments, participants, rating (future), and tags (future).
3. **Areas**: Instead of just pinpointing a single location, allow the definition of an "area" centered on a location, with a radius.
4. **Multiple Locations**: Instead of just pinpointing a single location, allow multiples. Maybe multiple areas as well?
5. **Share**: Each video should have a unique link that will navigate to the map, with the video location centered, and pop-up the dialog for that video.
6. **Related videos**: Inspired by the [Harley Davidson dealer locator](https://www.harley-davidson.com/us/en/tools/find-a-dealer.html), display a list of temporal-spatially related videos when clicking on a marker.
5. **Video trim**: Indicate when the critical scene is in the timeline. This does not alter the original video.
6. **Problem Flag**: Indicate if the encounters had issues or were relatively smooth. Use neutral terminology to avoid editorial bias.

    Suggested values

    -- Smooth / Cooperative  
    -- Mixed / Unclear  
    -- Contentious / Problematic  
7. **Original Video Link**: Useful for re-audits, re-cuts, or analyses of original video. Works best if the original video has already been approved in the system. If not, maybe we can auto-import it into a pending moderation state? Might even be nice to link multiple videos, especially for analyses of a long process.
8. **Rating System**: Collect rating of encounter. Include the auditor rating and government official rating. Use defined scales and guidance text to reduce subjectivity.
9. **Tag System**: Allow video submitters and moderators to tag videos (before publishing?). Perhaps new tags are separately moderated? Any existing tags can be used.

## Security

1. **Change email**: Allow non-OAuth users to change their email address. Will require a new process so their old address is not overwritten until their new address has been verified.
2. **Change password**: Allow non-OAuth users to change their password. Should require them to re-validate their old password, and enter their new password twice.

## AI

1. **Natural Language Search**: Allow users to enter plain-language queries (e.g., “4th Amendment audits near Phoenix last year”) which are translated into structured search filters using NLP/LLMs. Probably only for Pro users, because of the potential cost. Results should be explainable (“Showing results based on…”)

## Social

1. **Primary Social Accounts**  
   Create and maintain official accounts on:
   - YouTube
   - Facebook
2. **Secondary Social Accounts**
   - Instagram
   - Reddit
3. **Tertiary Accounts**
   - X (Twitter)
   - BlueSky
   - Discord
4. **Group Notifications**: Automatically publish notifications to chat services (Facebook, Reddit, X, BlueSky, Discord) when new videos are approved for respected auditors. Requires careful rate limiting and platform-specific formatting. Avoid sensational framing
5. **Personal Notifications**: Like below, but targeted to social media accounts. Requires collecting and verifying their account info. Requires account verification. Opt-in only

## Notifications

1. **Promotions**: Notify users when they are promoted and celebrate!
2. **Upsell**: Gently notify promoted users they can go Pro. No hard sell. Opt-out respected
3. **Unsubscribe**: Allow users to unsubscribe from all future messages. Linked in all messages sent.
4. **Public Daily summary**: Allow registered users (as long as we know their email) to request daily email notifications that contain the day's latest additions. Consider CAN-SPAM. Possibly use a 3rd party.
5. **Custom Daily summary**: Allow registered users (as long as we know their email) to request email notifications when new videos in a defined area are approved. Allow other filter criteria as well. Possibly only for Pro users. Consider CAN-SPAM.
6. **Email templates**: Functionality probably provided by email notification provider, otherwise build custom.
7. **Immediate notification**: Email or SMS when a new video is approved with less delay (hourly job?). Pro users only.
8. **Bounce Handling**: What do we do when we can't deliver emails to someone? Message at their next login?

## Import

1. **Curated Auditors**: Create a curated table of the respected auditors. “Respected” indicates curation, not endorsement.
2. **Seed Imports**:
    - Populate the curated auditors table with the largest, most respected auditors (like LIA and HYO). Determine how far back we want to go with imports.
    - Create a job to import existing videos from curated auditors table. Seeds the DB with quality. Learning experience.
    - Add **more** curated auditors (like AtA, LackLuster, AP, James Freeman, etc). Gets a critical mass.
3. **Expansion of Curated Auditors**  
   Gradually add additional respected auditors (e.g., AtA, AP, James Freeman, James Madison) to reach critical mass.
4. **Ongoing**: Create a new job for daily query for additional videos from curated auditors.

## Monetization
See [ChatGPT suggestions](https://chatgpt.com/share/6981a103-1008-8010-bc2d-06927edbf2f9)

1. **Donations**: Unobtrusive soft request at the bottom of each page. A donation page should break down actual costs.
2. **Advertising**: Keep these simple as well, and only focus on appropriate product and service categories. Avoid political or inflammatory advertising.
3. **Pro Users**: Keep the price low. Soft positioning (capability unlocks, not exclusion). Try to make the features compelling. Possibly a link to Patreon? Requires some form of payment processing. Keep it simple.

## Legal

1. **Privacy Policy**: A versioned and dated document that outlines what we do with the data we collect. The latest is visible to all users.
2. **Terms and Conditions**: A versioned and dated document new users must agree to when they register. Record the acceptance timestamp and the version. Old versions remain accessible.


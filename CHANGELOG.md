## CHANGELOG

### GitHub Release Versioning

As of v3.0.7, this module will document all changes within the GitHub release information to avoid duplication.

### [v3.2.0] Breaking Changes

#### Minimum Python Version

- Dropped support for <3.9

- `NodeBase` `._id` attribute renamed to `_address`, continue to use `address` property.
- `Folder` `._id` attribute renamed to `_address`, continue to use `address` property.

#### Nodes

- No longer support direct setting of `status` property, use `update_status`

#### Programs

- No longer support direct setting of `last_edited` property, use `update_last_edited`
- No longer support direct setting of `status` property, use `update_status`

#### Variables

- No longer support direct setting of `status` property, use `update_status`

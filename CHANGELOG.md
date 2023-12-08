# Changelog

## [1.17.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.16.2...v1.17.0) (2023-12-08)


### Features

* add dev mode to override images ([227ccde](https://www.github.com/GluuFederation/community-edition-containers/commit/227ccdefe81c0bc9053db1cbd5ceb93921041682)), closes [#62](https://www.github.com/GluuFederation/community-edition-containers/issues/62)


### Bug Fixes

* handle AttributeError: cython_sources caused by pyyaml builds ([74b7c60](https://www.github.com/GluuFederation/community-edition-containers/commit/74b7c60f2f484d455972152531c24395d66dabfb))
* incorrect service name for postgresql ([5674803](https://www.github.com/GluuFederation/community-edition-containers/commit/5674803167cc836860ea5a51921cfae09c6d98d1))


### Miscellaneous Chores

* update image tags to v4.5.3 ([#63](https://www.github.com/GluuFederation/community-edition-containers/issues/63)) ([2676277](https://www.github.com/GluuFederation/community-edition-containers/commit/26762778291a1dfd4da6f7dbcbe22958080ce394))

### [1.16.2](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.16.1...v1.16.2) (2023-09-14)


### Features

* add autoheal support to restart unhealthy containers ([#61](https://www.github.com/GluuFederation/community-edition-containers/issues/61)) ([0b45a48](https://www.github.com/GluuFederation/community-edition-containers/commit/0b45a48144f49b7021ccf4f795a887f101ba9fbf))
* add healthcheck directive in compose files ([#58](https://www.github.com/GluuFederation/community-edition-containers/issues/58)) ([3bd6f60](https://www.github.com/GluuFederation/community-edition-containers/commit/3bd6f606ba4076a014aef0b6f48bb0956c56576b))


### Miscellaneous Chores

* update oxauth and config-init image tag ([a5b3ab4](https://www.github.com/GluuFederation/community-edition-containers/commit/a5b3ab4bf4713e02b9ec6987053c080c89cf2e0e))

### [1.16.1](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.16.0...v1.16.1) (2023-09-04)


### Features

* update persistence image tag ([a91a237](https://www.github.com/GluuFederation/community-edition-containers/commit/a91a237dab2ac0f3212d5ba351160d169e2250ac))

## [1.16.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.15.1...v1.16.0) (2023-08-31)


### Miscellaneous Chores

* bump version to 1.16.0 ([0091ab1](https://www.github.com/GluuFederation/community-edition-containers/commit/0091ab1372c97dbd6d1d5c6663c22cac2131098f))
* update image tags to v4.5.2 ([0cbaeaf](https://www.github.com/GluuFederation/community-edition-containers/commit/0cbaeafbaff13b2acf5a4c1c52b9cefa0c6ce799))

### [1.15.1](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.14.4...v1.15.1) (2023-06-19)


### Bug Fixes

* error while fetching server API version in new installation ([03217ef](https://www.github.com/GluuFederation/community-edition-containers/commit/03217efb765f94c383251ffd4aa9b65cd5e8bc0a))
* removed duplicate key restart ([#51](https://www.github.com/GluuFederation/community-edition-containers/issues/51)) ([3e98cda](https://www.github.com/GluuFederation/community-edition-containers/commit/3e98cdaa07c1d614862873c4d29cb0d8508addcc))


### Miscellaneous Chores

* bump version to 1.15.1 ([ed38b6d](https://www.github.com/GluuFederation/community-edition-containers/commit/ed38b6d6c73ec8ae94ef98082fe9a134506f69c0))
* update image tags to v4.5.1-1 ([c72df5b](https://www.github.com/GluuFederation/community-edition-containers/commit/c72df5bfa51b6d6d686896e9b847b336b0c5d934))

### [1.14.4](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.14.3...v1.14.4) (2023-02-28)


### Miscellaneous Chores

* update image tags to v4.5.0-5+ ([df559b7](https://www.github.com/GluuFederation/community-edition-containers/commit/df559b76aabaa6170bc5f64dda2475101e7ba6bf))

### [1.14.3](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.14.2...v1.14.3) (2023-02-06)


### Miscellaneous Chores

* update image tags to v4.5.0-4+ ([3cd7b56](https://www.github.com/GluuFederation/community-edition-containers/commit/3cd7b56bca0debf25c7f5c2cc99ca3bec491405f))

### [1.14.2](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.14.1...v1.14.2) (2023-01-18)


### Features

* expose Vault port to host loopback interface ([084f430](https://www.github.com/GluuFederation/community-edition-containers/commit/084f430045253e580fa08abbfd9b6524d18622e3))
* set consul client address and port for easy access ([8d50f70](https://www.github.com/GluuFederation/community-edition-containers/commit/8d50f703afcbd48a9a4aee1dcf891f151386eb84))


### Miscellaneous Chores

* bump version to 1.14.2 ([8caed3a](https://www.github.com/GluuFederation/community-edition-containers/commit/8caed3ace2fc1a556831788ede73e76e71844ad5))
* update image tags to v4.5.0-3+ ([55ad2e2](https://www.github.com/GluuFederation/community-edition-containers/commit/55ad2e220ed55bd63ae57e007b65624d41ed8fb9))

### [1.14.1](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.14.0...v1.14.1) (2023-01-01)


### Miscellaneous Chores

* bump version and compatibility matrix ([b06653b](https://www.github.com/GluuFederation/community-edition-containers/commit/b06653bdd2b2cd748bedd71e73428f0af0f04355))

## [1.14.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.13.0...v1.14.0) (2022-12-08)


### Bug Fixes

* update tags to v4.2.2-2 ([e84e915](https://www.github.com/GluuFederation/community-edition-containers/commit/e84e915990f19457686be923a64068bce8c07836))


### Documentation

* update changelog ([aadec04](https://www.github.com/GluuFederation/community-edition-containers/commit/aadec0446f633bdb9e0aa85ec302604283f1e00e))
* update reference to branch 4.5 ([393dd58](https://www.github.com/GluuFederation/community-edition-containers/commit/393dd583f543416beedd8d11aa1bb92c1a7d01d1))


### Miscellaneous Chores

* bump version and compatibility matrix ([b5df784](https://www.github.com/GluuFederation/community-edition-containers/commit/b5df7840191eb5b5d1d3c309e03e4ad10e7ef08c))
* bump version and compatibility matrix ([e522a3a](https://www.github.com/GluuFederation/community-edition-containers/commit/e522a3a645d0d5580557adc096035d653342ba1e))

### [1.13.1](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.13.0...v1.13.1) (2022-11-30)


### Bug Fixes

* update tags to v4.2.2-2 ([e84e915](https://www.github.com/GluuFederation/community-edition-containers/commit/e84e915990f19457686be923a64068bce8c07836))


### Miscellaneous Chores

* bump version and compatibility matrix ([e522a3a](https://www.github.com/GluuFederation/community-edition-containers/commit/e522a3a645d0d5580557adc096035d653342ba1e))

## [1.13.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.12.0...v1.13.0) (2022-11-11)


### Features

* update image tags to v4.4.2-1 ([7a891fb](https://www.github.com/GluuFederation/community-edition-containers/commit/7a891fbcd8b188104b6e670350a669eaff726a3a))


### Bug Fixes

* set socket default timeout to avoid stale connection ([d892d20](https://www.github.com/GluuFederation/community-edition-containers/commit/d892d20be600e7e50ea6642da0fa5ae6e2692b68))


### Miscellaneous Chores

* bump version and compatibility matrix ([d3d8cc5](https://www.github.com/GluuFederation/community-edition-containers/commit/d3d8cc5346848af025308afc930eb9cd668a9b35))

## [1.12.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.11.0...v1.12.0) (2022-08-01)

### Features

* update image tags to 4.4.1-1 (compatible with Gluu Server 4.4.1)([8f82ee9](https://github.com/GluuFederation/community-edition-containers/commit/8f82ee9608a2b0a7860ada6aa5cec1bf55b2294e))

### Documentation

* add compatibility matrix between pygluu-compose and Gluu Server ([209c20d](https://www.github.com/GluuFederation/community-edition-containers/commit/209c20d880f8999dc3df00ef2c53af66315c1157))
* add missing docstrings ([afe51a0](https://www.github.com/GluuFederation/community-edition-containers/commit/afe51a06404c41249ecf2bc1bd74c6f1018be4e4))

## [1.11.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.10.0...v1.11.0) (2022-05-05)


### Features

* add mysql service ([a92657d](https://www.github.com/GluuFederation/community-edition-containers/commit/a92657d44491c1d9aacfd2cd8eb4f517f0012945))
* add SPANNER_EMULATOR_HOST config ([bbebfd8](https://www.github.com/GluuFederation/community-edition-containers/commit/bbebfd88e379e0f7f506b73c8a1ac9a2ac76f2c2))


### Bug Fixes

* versioning number ([3412a60](https://www.github.com/GluuFederation/community-edition-containers/commit/3412a607e04fe0c03593d2d7edea2c20b1547bbc))


### Miscellaneous Chores

* update image tags ([048de2c](https://www.github.com/GluuFederation/community-edition-containers/commit/048de2ce7dba89beca57227d1bb17ec43f7b4766))

## [1.10.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.9.0...v1.10.0) (2022-03-27)


### Miscellaneous Chores

* update oxauth, oxtrust, and jackrabbit tags ([6714148](https://www.github.com/GluuFederation/community-edition-containers/commit/67141480e3670d3ca62ecc908e3788d98eed7cfa))

## [1.9.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.8.0...v1.9.0) (2022-02-10)


### Features

* update image tags to Gluu 4.3.1 ([e943627](https://www.github.com/GluuFederation/community-edition-containers/commit/e943627d378fc28256e84aa08fc93a0c8d5e9206))


### Miscellaneous Chores

* update nginx image tag ([0beb6f0](https://www.github.com/GluuFederation/community-edition-containers/commit/0beb6f0260fc5ae894122015f2920c0d73200e91))

## [1.8.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.7.0...v1.8.0) (2021-11-29)


### Features

* introduce dynamic container configuration (Gluu 4.3) ([#33](https://www.github.com/GluuFederation/community-edition-containers/issues/33)) ([c2f1f6b](https://www.github.com/GluuFederation/community-edition-containers/commit/c2f1f6bcda4486288ae1a15ec14d2116ff07e753))

## [1.7.0](https://www.github.com/GluuFederation/community-edition-containers/compare/v1.6.1...v1.7.0) (2021-10-05)


### Features

* add config and secrets manifest for jackrabbit service ([abac12c](https://www.github.com/GluuFederation/community-edition-containers/commit/abac12ca44f572039f6ff5f9f02a3fd1bb8d2b2a))
* add sql and spanner support ([82d8d52](https://www.github.com/GluuFederation/community-edition-containers/commit/82d8d527e60146c058a29bc1c8c792e0517475de))
* **images:** update reference to latest images ([d68a714](https://www.github.com/GluuFederation/community-edition-containers/commit/d68a7147c398dbc4139666a7b4f0df763c10b6eb))
* **images:** update reference to latest images ([d815b71](https://www.github.com/GluuFederation/community-edition-containers/commit/d815b711e3ae8de2cd4fe00a6868b78c5efcd4d5))
* introduce scim protection mode ([901b66e](https://www.github.com/GluuFederation/community-edition-containers/commit/901b66e7a0aeb8aff2f6d4a2ed08906e49f9fbcb))
* **manifests:** initial work on Gluu Server v4.3 support ([5e631c3](https://www.github.com/GluuFederation/community-edition-containers/commit/5e631c3303c8504365f6a78af34444198219fc68))
* remove radius service ([357b51f](https://www.github.com/GluuFederation/community-edition-containers/commit/357b51fede38461eda137c4b827cd89b8b23a285))


### Bug Fixes

* **auto-unseal:** get recovery key instead of unseal key; closes [#26](https://www.github.com/GluuFederation/community-edition-containers/issues/26) ([d96fc83](https://www.github.com/GluuFederation/community-edition-containers/commit/d96fc83d34902a48002c4d0fd8f60b24b48fea6c))
* **cli:** resolve app version from version.py module ([c76861e](https://www.github.com/GluuFederation/community-edition-containers/commit/c76861ed4525a432ac39a3d84e5036685353f5bb))


### Documentation

* fix URL on workflow badge ([90d37f8](https://www.github.com/GluuFederation/community-edition-containers/commit/90d37f89214fdcc88d513efc00001ba68b9c538c))
* **install:** refer to official docs for installation ([e035250](https://www.github.com/GluuFederation/community-edition-containers/commit/e03525032bad6d4ed27319c565872c1ad693aca6))

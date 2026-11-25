name: Android CI

on:
  push:
    branches: [main, master]

  pull_request:
    branches: [main, master]

  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: keyflow-ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

env:
  PROJECT_DIR: KeyFlow

jobs:
  build-test-lint:
    name: Build, Unit Tests and Lint
    runs-on: ubuntu-24.04
    timeout-minutes: 60

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Generate KeyFlow project
        shell: bash
        run: |
          set -euo pipefail
          python3 create_keyflow_Telecom_FakeCall.py .
          test -f "$PROJECT_DIR/gradlew"
          test -f "$PROJECT_DIR/app/build.gradle.kts"
          test -f "$PROJECT_DIR/tools/ci_prepare_metadata.sh"
          test -f "$PROJECT_DIR/tools/ci_instrumented.sh"

      - name: Run static QA
        shell: bash
        run: |
          set -euo pipefail
          cd "$PROJECT_DIR"
          python3 tools/qa_static_check.py

      - name: Set up JDK 17
        uses: actions/setup-java@v5
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          build-root-directory: ${{ env.PROJECT_DIR }}

      - name: Verify Gradle Wrapper
        shell: bash
        run: |
          set -euo pipefail
          cd "$PROJECT_DIR"
          chmod +x gradlew
          ./gradlew --version

      - name: Generate or verify dependency locks and Room schema
        shell: bash
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          set -euo pipefail
          bash tools/ci_prepare_metadata.sh

      - name: Run Unit Tests, Lint and Debug Build
        shell: bash
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          set -euo pipefail
          bash tools/ci_gradle.sh \
            :app:testDebugUnitTest \
            :app:lintDebug \
            :app:assembleDebug

      - name: Verify reproducibility metadata
        if: success()
        shell: bash
        working-directory: ${{ env.PROJECT_DIR }}
        run: |
          set -euo pipefail
          python3 tools/verify_reproducibility_metadata.py --require-complete

      - name: Upload reports and metadata
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: keyflow-build-reports
          path: |
            KeyFlow/app/gradle.lockfile
            KeyFlow/app/schemas/**/1.json
            KeyFlow/app/build/reports/**
            KeyFlow/app/build/test-results/**
          if-no-files-found: ignore
          retention-days: 14

      - name: Upload Debug APK
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: keyflow-debug-apk
          path: KeyFlow/app/build/outputs/apk/debug/*.apk
          if-no-files-found: error
          retention-days: 14

  instrumented-tests:
    name: Instrumented Tests - Android Emulator
    needs: build-test-lint
    runs-on: macos-14
    timeout-minutes: 75

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Generate KeyFlow project
        shell: bash
        run: |
          set -euo pipefail
          python3 create_keyflow_Telecom_FakeCall.py .
          test -f "$PROJECT_DIR/gradlew"
          test -f "$PROJECT_DIR/app/build.gradle.kts"
          test -f "$PROJECT_DIR/tools/ci_instrumented.sh"

      - name: Set up JDK 17
        uses: actions/setup-java@v5
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          build-root-directory: ${{ env.PROJECT_DIR }}

      - name: Run instrumented tests on Android Emulator
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 35
          arch: x86_64
          target: google_apis
          cores: 2
          avd-name: keyflow-ci
          force-avd-creation: true
          emulator-boot-timeout: 600
          disable-animations: true
          working-directory: KeyFlow
          script: bash tools/ci_instrumented.sh

      - name: Upload instrumentation reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: keyflow-instrumented-reports
          path: |
            KeyFlow/app/build/reports/**
            KeyFlow/app/build/test-results/**
          if-no-files-found: ignore
          retention-days: 14

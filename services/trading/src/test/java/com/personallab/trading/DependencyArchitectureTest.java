package com.personallab.trading;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

@AnalyzeClasses(packages = "com.personallab.trading", importOptions = ImportOption.DoNotIncludeTests.class)
class DependencyArchitectureTest {
    @ArchTest
    static final ArchRule domainDoesNotDependOnAdaptersOrSpring = noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..web..", "..infrastructure..", "..config..", "org.springframework..");
}

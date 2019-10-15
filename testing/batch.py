"""
This example is from doi:10.1021/acscatal.7b03205, Huber et al.

ethylene dimerization and oligomerization to 1 butene
"""
# load a bunch of stuff
import cantera as ct
import numpy as np
import scipy
import pylab
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.pyplot import cm
from matplotlib.ticker import NullFormatter, MaxNLocator, LogLocator
plt.switch_backend('agg')  # needed for saving figures
import csv
from pydas.dassl import DASSL
import os

import re
import operator
import pandas as pd
import pylab
from cycler import cycler
import seaborn as sns
import os
import multiprocessing
import sys

# this chemkin file is from the cti generated by rmg
gas = ct.Solution('./chem_annotated.cti', 'gas')
surf = ct.Interface('./chem_annotated.cti', 'surface1', [gas])

print("This mechanism contains {} gas reactions and {} surface reactions".format(gas.n_reactions, surf.n_reactions))

i_c2h4 = gas.species_index('C2H4(2)')
i_nheptane = gas.species_index('n-heptane')
i_c4h8_1 = gas.species_index('C4H8-1(3)') # 1 butene
i_c4h8_2 = gas.species_index('C4H8-2(4)')

# unit conversion factors to SI
mm = 0.001
cm = 0.01
ms = mm
minute = 60.0

#######################################################################
# Input Parameters
#######################################################################
t_in = 423  # K, uniform temperature profile
t_cat = t_in
cat_area_per_vol = 5.9e8  # in m-1

def batch(gas, surf, temp, mol_in, verbose=False, sens=False):
    volume = 0.3 # L or m^3
    cat_area = cat_area_per_vol * volume
    T0 = temp
    pressure = 35  # bar
    pressure = pressure * 1e6  # Pascal
    P0 = pressure  # Pa
    c2h4, nh = mol_in
    c2h4 = str(c2h4)
    nh = str(nh)
    X = str('C2H4(2):' + c2h4 + ', n-heptane:' + nh)  # gas concentrations

    gas.TPX = temp, P0, X
    temp_cat = temp
    surf.TP = temp_cat, P0
    surf.coverages = 'X(1):1.0'

    gas_names = gas.species_names
    surf_names = surf.species_names

    r = ct.IdealGasConstPressureReactor(gas, energy='off')
    r.volume = volume
    rsurf = ct.ReactorSurface(surf, r, A=cat_area)

    sim = ct.ReactorNet([r])
    sim.max_err_test_fails = 12

    # set relative and absolute tolerances on the simulation
    sim.rtol = 1.0e-12
    sim.atol = 1.0e-18

    # rxn_time = np.linspace(1E-12, 5, 10001)
    rxn_time = np.logspace(-5, np.log10(3600), 1000001) #from 0s to 3600s (1 hour), log spacing\n",
    gas_mole_fracs = np.zeros([gas.n_species, len(rxn_time)])
    surf_site_fracs = np.zeros([surf.n_species, len(rxn_time)])
    temperature = np.zeros(len(rxn_time))
    pressure = np.zeros(len(rxn_time))

    if verbose is True:
        print('  distance(mm)   X_C2H4       X_C4H8-1')

    surf.set_multiplier(1.0)
    if sens is not False:
        surf.set_multiplier(1.0 + sens[0], sens[1])
    for i in range(len(rxn_time)):
        time = rxn_time[i] #define time in the reactor
        sim.advance(time) #Advance the simulation to next set time\n",
        temperature[i] = gas.T
        pressure[i] = gas.P/ct.one_atm
        gas_mole_fracs[:,i] = gas.X
        surf_site_fracs[:,i] = surf.coverages

        if verbose is True:
            if not i % 1000:
                print('  {0:10f}  {1:10f} '.format(time, *gas[
                    'C2H4(2)', 'C4H8-1(3)'].X))

    surf.set_multiplier(1.0)  # resetting things

    return gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time, temperature

def semibatch(gas, surf, temp, mol_in, verbose=False, sens=False):
    p = 35  # bar
    pressure = p * 1e6 # Pascal
    volume = 0.3  # Liter or m^3
    cat_area = cat_area_per_vol * volume

    c2h4, nh = mol_in
    c2h4 = str(c2h4)
    nh = str(nh)
    X = str('C2H4(2):' + c2h4 + ', n-heptane:' + nh)  # gas concentrations

    gas.TPX = temp, pressure, 'C2H4(2):1'  # pure ethylene for the reservoir
    surf.TP = temp, pressure
    surf.coverages = 'X(1):1.0'

    gas_names = gas.species_names
    surf_names = surf.species_names

    # create an upstream reservoir that will supply the sreactor. The temperature,
    # pressure, and composition of the upstream reservoir are set to those of the
    # 'gas' object at the time the reservoir is created.
    upstream = ct.Reservoir(gas)  # only ethylene

    # set the gas to the specified input concentrations
    gas.TPX = temp, pressure, X

    # Now create the reactor object with a differnet initial state.  Turn energy off
    # so the temperature stays at its initial value
    r = ct.IdealGasReactor(gas, energy='off')

    # Set its volume. In this problem, the reactor volume is fixed, so
    # the initial volume is the volume at all later times.
    r.volume = volume

    # Add the reacting surface to the reactor. The area is set to the desired
    # catalyst area in the reactor.
    rsurf = ct.ReactorSurface(surf, r, A=cat_area)

    # create a valve to feed in ethylene from the reservoir to the reactor
    pressureRegulator = ct.Valve(upstream=upstream,
                                 downstream=r,
                                 K=1e-4)

    sim = ct.ReactorNet([r])
    sim.max_err_test_fails = 12

    # set relative and absolute tolerances on the simulation
    sim.rtol = 1.0e-10
    sim.atol = 1.0e-20

    # rxn_time = np.linspace(1E-12, 5, 10001)
    rxn_time = np.logspace(-5, np.log10(3600), 1000001) #from 0s to 3600s (1 hour), log spacing\n",
    gas_mole_fracs = np.zeros([gas.n_species, len(rxn_time)])
    surf_site_fracs = np.zeros([surf.n_species, len(rxn_time)])
    pressure = np.zeros(len(rxn_time))

    if verbose is True:
        print('  distance(mm)   X_C2H4       X_C4H8-1')

    surf.set_multiplier(1.0)
    if sens is not False:
        surf.set_multiplier(1.0 + sens[0], sens[1])
    for i in range(len(rxn_time)):
        time = rxn_time[i] #define time in the reactor
        sim.advance(time) #Advance the simulation to next set time\n",
        pressure[i] = gas.P/ct.one_atm
        gas_mole_fracs[:,i] = gas.X
        surf_site_fracs[:,i] = surf.coverages

        if verbose is True:
            if not i % 1000:
                print('  {0:10f}  {1:10f} '.format(time, *gas[
                    'C2H4(2)', 'C4H8-1(3)'].X))

    surf.set_multiplier(1.0)  # resetting things
    return gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time

def plot(gas, surf, gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time):
    #Plot out simulations results
    fig = pylab.figure(dpi=300,figsize=(8,8))
    gs = gridspec.GridSpec(2, 1)
    ax0 = plt.subplot(gs[0])
    ax1 = plt.subplot(gs[1])

    y_min = 1E-4

    for i in range(gas.n_species):
        if np.max(gas_mole_fracs[i,:]) > y_min:
            ax0.loglog(rxn_time, gas_mole_fracs[i,:], label=gas.species_name(i) )

    for i in range(surf.n_species):
        if np.max(surf_site_fracs[i,:]) > y_min:
            ax1.loglog(rxn_time, surf_site_fracs[i,:], label=surf.species_name(i) )

    ax0.legend(loc='lower left', fontsize = 12)
    ax1.legend(loc='lower left', fontsize = 12)

    ax0.set_ylabel("gas-phase mole fraction")
    ax0.set_ylim(y_min,1.)
    ax0.set_xlim(1.0E-4,max(rxn_time))
    ax1.set_xlim(1.0E-4,max(rxn_time))
    ax0.set_xlabel("Time(s)")
    ax1.set_ylabel("surface site fraction")
    #ax0.xaxis.set_major_locator(MaxNLocator(6))
    #ax0.yaxis.set_major_locator(LogLocator(base=10.0, numticks=3))
    #ax0.tick_params(axis='both', which='major', labelsize=10)
    ax1.set_ylim(y_min, 2)
    ax1.set_xlabel("Time(s)")
    fig.savefig('./figures/batch.pdf', bbox_inches='tight')


f_ethylene = 0.67
f_nheptane = 0.33
ratio_in = [f_ethylene, f_nheptane]

# a = batch(gas, surf, t_in, ratio_in)
# gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time, temperature = a
# plot(gas, surf, gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time, temperature)

a = semibatch(gas, surf, t_in, ratio_in)
gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time = a
plot(gas, surf, gas_mole_fracs, surf_site_fracs, gas_names, surf_names, rxn_time)

# sys.exit("Stop here")

# # for sens at end of time
# ethylene_in_ref = gas_mole_fracs[i_c2h4,:0]
# ethylene_out_ref = gas_mole_fracs[i_c2h4,:-1]
# etylene_depletion_ref = ethylene_in_ref - ethylene_out_ref
# ethylene_conv_ref = ethylene_depletion_ref / ethylene_in_ref
# butene1_out_ref = gas_mole_fracs[i_c4h8_1,:-1]
# butene1_sel_ref = butene1_out_ref / (ethylene_depletion_ref * 0.5)  # todo: check to make sure this is correct
# butene2_out_ref = gas_mole_fracs[i_c4h8_2,:-1]
# butene2_sel_ref = butene2_out_ref / (ethylene_depletion_ref * 0.5)  # todo: check to make sure this is correct
# ## c6, c8 etc
#
# # for sens the way it was defined in
# # https://raw.githubusercontent.com/mazeau/surface_w_sensitivity/ethylene/batch_surface_w_sensitivity_v0.ipynb
# ethylene_ref = gas_mole_fracs[i_c2h4,:]
#
# # set the value of the perturbation
# dk = 1.0e-2
# sensitivity1 = []  # ethylene conversion, 1-butene selectivity, ...
# sensitivity2 = []
#
# for m in range(surf.n_reactions):
#     sens = [dk, m]
#     b = batch(gas, surf, t_in, ratio_in, sens)
#     gas_mole_fracs_new, surf_site_fracs_new, gas_names, surf_names, rxn_time, temperature_new = b
#
#     ethylene_in = gas_mole_fracs_new[i_c2h4,:0]
#     ethylene_out = gas_mole_fracs_new[i_c2h4,:-1]
#     ethylene_depletion = (ethylene_in - ethylene_out)
#     ethylene_conv = ethylene_depletion / ethylene_in
#     butene1_out = gas_mole_fracs_new[i_c4h8_1,:-1]
#     butene1_sel = butene1_out / (ethylene_depletion * 0.5)  # todo: check to make sure this is correct
#     butene2_out = gas_mole_fracs_new[i_c4h8_2,:-1]
#     butene2_sel = butene2_out / (ethylene_depletion * 0.5)  # todo: check to make sure this is correct
#
#     # for the old sensitivity def
